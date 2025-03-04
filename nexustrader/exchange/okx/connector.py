import msgspec
import sys
from typing import Dict
from decimal import Decimal
from nexustrader.exchange.okx import OkxAccountType
from nexustrader.exchange.okx.websockets import OkxWSClient
from nexustrader.exchange.okx.exchange import OkxExchangeManager
from nexustrader.exchange.okx.schema import OkxWsGeneralMsg
from nexustrader.schema import Trade, BookL1, Kline, Order, Position
from nexustrader.exchange.okx.schema import (
    OkxMarket,
    OkxWsBboTbtMsg,
    OkxWsCandleMsg,
    OkxWsTradeMsg,
    OkxWsOrderMsg,
    OkxWsPositionMsg,
    OkxWsAccountMsg,
    OkxBalanceResponse,
    OkxPositionResponse,
    OkxCandlesticksResponse,
    OkxCandlesticksResponseData
)
from nexustrader.constants import (
    OrderStatus,
    TimeInForce,
    PositionSide,
    KlineInterval,
    TriggerType,
)
from nexustrader.base import PublicConnector, PrivateConnector
from nexustrader.core.nautilius_core import MessageBus
from nexustrader.core.cache import AsyncCache
from nexustrader.core.entity import TaskManager, RateLimit
from nexustrader.exchange.okx.rest_api import OkxApiClient
from nexustrader.constants import OrderSide, OrderType
from nexustrader.exchange.okx.constants import (
    OkxTdMode,
    OkxEnumParser,
    OkxKlineInterval,
)


class OkxPublicConnector(PublicConnector):
    _ws_client: OkxWSClient
    _api_client: OkxApiClient
    _account_type: OkxAccountType

    def __init__(
        self,
        account_type: OkxAccountType,
        exchange: OkxExchangeManager,
        msgbus: MessageBus,
        task_manager: TaskManager,
        rate_limit: RateLimit | None = None,
    ):
        super().__init__(
            account_type=account_type,
            market=exchange.market,
            market_id=exchange.market_id,
            exchange_id=exchange.exchange_id,
            ws_client=OkxWSClient(
                account_type=account_type,
                handler=self._ws_msg_handler,
                task_manager=task_manager,
            ),
            msgbus=msgbus,
            api_client=OkxApiClient(
                testnet=account_type.is_testnet,
            ),
            task_manager=task_manager,
            rate_limit=rate_limit,
        )
        self._business_ws_client = OkxWSClient(
            account_type=account_type,
            handler=self._business_ws_msg_handler,
            task_manager=task_manager,
            business_url=True,
        )
        self._ws_msg_general_decoder = msgspec.json.Decoder(OkxWsGeneralMsg)
        self._ws_msg_bbo_tbt_decoder = msgspec.json.Decoder(OkxWsBboTbtMsg)
        self._ws_msg_candle_decoder = msgspec.json.Decoder(OkxWsCandleMsg)
        self._ws_msg_trade_decoder = msgspec.json.Decoder(OkxWsTradeMsg)

    async def _request_klines(
        self,
        symbol: str,
        interval: KlineInterval,
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        if self._limiter:
            await self._limiter.acquire()
        
        okx_interval = OkxEnumParser.to_okx_kline_interval(interval)
        
        end_time_ms = int(end_time) if end_time is not None else sys.maxsize
        limit = int(limit) if limit is not None else 500
        all_klines: list[Kline] = []
        while True:
            klines_response: OkxCandlesticksResponse = await self._api_client.get_api_v5_market_candles(
                instId=self._market[symbol].id,
                bar=okx_interval.value,
                limit=limit,
                after=end_time,
                before=start_time,
            )
            klines: list[Kline] = [
                self._handle_candlesticks(
                    symbol=symbol, interval=interval, kline=kline
                )
                for kline in klines_response.data
            ]
            all_klines.extend(klines)

            # Update the start_time to fetch the next set of bars
            if klines:
                next_start_time = klines[0].start + 1
            else:
                # Handle the case when klines is empty
                break

            # No more bars to fetch
            if (limit and len(klines) < limit) or next_start_time >= end_time_ms:
                break

            start_time = next_start_time

        return all_klines
        
        
    def request_klines(
        self,
        symbol: str,
        interval: KlineInterval,
        limit: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[Kline]:
        return self._task_manager._loop.run_until_complete(
            self._request_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )
        )

    async def subscribe_trade(self, symbol: str):
        market = self._market.get(symbol, None)
        if not market:
            raise ValueError(f"Symbol {symbol} not found in market")
        await self._ws_client.subscribe_trade(market.id)

    async def subscribe_bookl1(self, symbol: str):
        market = self._market.get(symbol, None)
        if not market:
            raise ValueError(f"Symbol {symbol} not found in market")
        await self._ws_client.subscribe_order_book(market.id, channel="bbo-tbt")

    async def subscribe_kline(self, symbol: str, interval: KlineInterval):
        market = self._market.get(symbol, None)
        if not market:
            raise ValueError(f"Symbol {symbol} not found in market")
        interval = OkxEnumParser.to_okx_kline_interval(interval)
        await self._business_ws_client.subscribe_candlesticks(market.id, interval)

    def _business_ws_msg_handler(self, raw: bytes):
        if raw == b"pong":
            self._business_ws_client._transport.notify_user_specific_pong_received()
            self._log.debug(f"Pong received:{str(raw)}")
            return
        try:
            ws_msg: OkxWsGeneralMsg = self._ws_msg_general_decoder.decode(raw)
            if ws_msg.is_event_msg:
                self._handle_event_msg(ws_msg)
            else:
                channel: str = ws_msg.arg.channel
                if channel.startswith("candle"):
                    self._handle_kline(raw)
        except msgspec.DecodeError:
            self._log.error(f"Error decoding message: {str(raw)}")

    def _ws_msg_handler(self, raw: bytes):
        if raw == b"pong":
            self._ws_client._transport.notify_user_specific_pong_received()
            self._log.debug(f"Pong received:{str(raw)}")
            return
        try:
            ws_msg: OkxWsGeneralMsg = self._ws_msg_general_decoder.decode(raw)
            if ws_msg.is_event_msg:
                self._handle_event_msg(ws_msg)
            else:
                channel: str = ws_msg.arg.channel
                if channel == "bbo-tbt":
                    self._handle_bbo_tbt(raw)
                elif channel == "trades":
                    self._handle_trade(raw)
                elif channel.startswith("candle"):
                    self._handle_kline(raw)
        except msgspec.DecodeError:
            self._log.error(f"Error decoding message: {str(raw)}")

    def _handle_event_msg(self, ws_msg: OkxWsGeneralMsg):
        if ws_msg.event == "error":
            self._log.error(f"Error code: {ws_msg.code}, message: {ws_msg.msg}")
        elif ws_msg.event == "login":
            self._log.debug("Login success")
        elif ws_msg.event == "subscribe":
            self._log.debug(f"Subscribed to {ws_msg.arg.channel}")

    def _handle_kline(self, raw: bytes):
        msg: OkxWsCandleMsg = self._ws_msg_candle_decoder.decode(raw)

        id = msg.arg.instId
        symbol = self._market_id[id]
        okx_interval = OkxKlineInterval(msg.arg.channel)
        interval = OkxEnumParser.parse_kline_interval(okx_interval)

        for d in msg.data:
            kline = Kline(
                exchange=self._exchange_id,
                symbol=symbol,
                interval=interval,
                open=float(d[1]),
                high=float(d[2]),
                low=float(d[3]),
                close=float(d[4]),
                volume=float(d[5]),
                start=int(d[0]),
                timestamp=self._clock.timestamp_ms(),
                confirm=False if d[8] == "0" else True,
            )
            self._msgbus.publish(topic="kline", msg=kline)

    def _handle_trade(self, raw: bytes):
        msg: OkxWsTradeMsg = self._ws_msg_trade_decoder.decode(raw)
        id = msg.arg.instId
        symbol = self._market_id[id]
        for d in msg.data:
            trade = Trade(
                exchange=self._exchange_id,
                symbol=symbol,
                price=float(d.px),
                size=float(d.sz),
                timestamp=int(d.ts),
            )
            self._msgbus.publish(topic="trade", msg=trade)

    def _handle_bbo_tbt(self, raw: bytes):
        msg: OkxWsBboTbtMsg = self._ws_msg_bbo_tbt_decoder.decode(raw)

        id = msg.arg.instId
        symbol = self._market_id[id]

        for d in msg.data:
            bookl1 = BookL1(
                exchange=self._exchange_id,
                symbol=symbol,
                bid=float(d.bids[0][0]),
                ask=float(d.asks[0][0]),
                bid_size=float(d.bids[0][1]),
                ask_size=float(d.asks[0][1]),
                timestamp=int(d.ts),
            )
            self._msgbus.publish(topic="bookl1", msg=bookl1)
    
    def _handle_candlesticks(self, symbol: str, interval: KlineInterval, kline: OkxCandlesticksResponseData) -> Kline:        
        return Kline(
            exchange=self._exchange_id,
            symbol=symbol,
            interval=interval,
            open=float(kline.o),
            high=float(kline.h),
            low=float(kline.l),
            close=float(kline.c),
            volume=float(kline.vol),
            quote_volume=float(kline.volCcyQuote),
            start=int(kline.ts),
            timestamp=self._clock.timestamp_ms(),
            confirm=False if int(kline.confirm) == 0 else True,
        )
            
    async def disconnect(self):
        await super().disconnect()
        self._business_ws_client.disconnect()


class OkxPrivateConnector(PrivateConnector):
    _ws_client: OkxWSClient
    _api_client: OkxApiClient
    _account_type: OkxAccountType
    _market: Dict[str, OkxMarket]
    _market_id: Dict[str, str]

    def __init__(
        self,
        exchange: OkxExchangeManager,
        account_type: OkxAccountType,
        cache: AsyncCache,
        msgbus: MessageBus,
        task_manager: TaskManager,
        rate_limit: RateLimit | None = None,
    ):
        if not exchange.api_key or not exchange.secret or not exchange.passphrase:
            raise ValueError(
                "API key, secret, and passphrase are required for private endpoints"
            )

        super().__init__(
            account_type=account_type,
            market=exchange.market,
            market_id=exchange.market_id,
            exchange_id=exchange.exchange_id,
            ws_client=OkxWSClient(
                account_type=account_type,
                handler=self._ws_msg_handler,
                task_manager=task_manager,
                api_key=exchange.api_key,
                secret=exchange.secret,
                passphrase=exchange.passphrase,
            ),
            api_client=OkxApiClient(
                api_key=exchange.api_key,
                secret=exchange.secret,
                passphrase=exchange.passphrase,
                testnet=account_type.is_testnet,
            ),
            msgbus=msgbus,
            cache=cache,
            rate_limit=rate_limit,
        )

        self._decoder_ws_general_msg = msgspec.json.Decoder(OkxWsGeneralMsg)
        self._decoder_ws_order_msg = msgspec.json.Decoder(OkxWsOrderMsg, strict=False)
        self._decoder_ws_position_msg = msgspec.json.Decoder(
            OkxWsPositionMsg, strict=False
        )
        self._decoder_ws_account_msg = msgspec.json.Decoder(
            OkxWsAccountMsg, strict=False
        )

    async def connect(self):
        await super().connect()
        await self._ws_client.subscribe_orders()
        await self._ws_client.subscribe_positions()
        await self._ws_client.subscribe_account()
        # await self._ws_client.subscribe_account_position()
        # await self._ws_client.subscribe_fills()

    async def _init_account_balance(self):
        res: OkxBalanceResponse = await self._api_client.get_api_v5_account_balance()
        for data in res.data:
            self._cache._apply_balance(self._account_type, data.parse_to_balances())

    async def _init_position(self):
        res: OkxPositionResponse = await self._api_client.get_api_v5_account_positions()
        for data in res.data:
            side = data.posSide.parse_to_position_side()
            if side == PositionSide.FLAT:
                signed_amount = Decimal(data.pos)
                if signed_amount > 0:
                    side = PositionSide.LONG
                elif signed_amount < 0:
                    side = PositionSide.SHORT
                else:
                    side = None
            elif side == PositionSide.LONG:
                signed_amount = Decimal(data.pos)
            elif side == PositionSide.SHORT:
                signed_amount = -Decimal(data.pos)

            symbol = self._market_id[data.instId]

            position = Position(
                symbol=symbol,
                exchange=self._exchange_id,
                side=side,
                signed_amount=signed_amount,
                entry_price=float(data.avgPx) if data.avgPx else 0,
                unrealized_pnl=float(data.upl) if data.upl else 0,
                realized_pnl=float(data.realizedPnl) if data.realizedPnl else 0,
            )
            self._cache._apply_position(position)

    def _handle_event_msg(self, msg: OkxWsGeneralMsg):
        if msg.event == "error":
            self._log.error(msg)
        elif msg.event == "login":
            self._log.info("Login success")
        elif msg.event == "subscribe":
            self._log.info(f"Subscribed to {msg.arg.channel}")

    def _ws_msg_handler(self, raw: bytes):
        if raw == b"pong":
            self._ws_client._transport.notify_user_specific_pong_received()
            self._log.debug(f"Pong received: {str(raw)}")
            return
        try:
            ws_msg: OkxWsGeneralMsg = self._decoder_ws_general_msg.decode(raw)
            if ws_msg.is_event_msg:
                self._handle_event_msg(ws_msg)
            else:
                channel = ws_msg.arg.channel
                if channel == "orders":
                    self._handle_orders(raw)
                elif channel == "positions":
                    self._handle_positions(raw)
                elif channel == "account":
                    self._handle_account(raw)
        except msgspec.DecodeError as e:
            self._log.error(f"Error decoding message: {str(raw)} {e}")

    def _handle_orders(self, raw: bytes):
        msg: OkxWsOrderMsg = self._decoder_ws_order_msg.decode(raw)
        self._log.debug(f"Order update: {str(msg)}")
        for data in msg.data:
            symbol = self._market_id[data.instId]
            order = Order(
                exchange=self._exchange_id,
                symbol=symbol,
                status=OkxEnumParser.parse_order_status(data.state),
                id=data.ordId,
                amount=Decimal(data.sz),
                filled=Decimal(data.accFillSz),
                client_order_id=data.clOrdId,
                timestamp=data.uTime,
                type=OkxEnumParser.parse_order_type(data.ordType),
                side=OkxEnumParser.parse_order_side(data.side),
                time_in_force=OkxEnumParser.parse_time_in_force(data.ordType),
                price=float(data.px) if data.px else None,
                average=float(data.avgPx) if data.avgPx else None,
                last_filled_price=float(data.fillPx) if data.fillPx else None,
                last_filled=Decimal(data.fillSz) if data.fillSz else Decimal(0),
                remaining=Decimal(data.sz) - Decimal(data.accFillSz),
                fee=Decimal(data.fee),  # accumalated fee
                fee_currency=data.feeCcy,  # accumalated fee currency
                cost=Decimal(data.avgPx) * Decimal(data.fillSz),
                cum_cost=Decimal(data.avgPx) * Decimal(data.accFillSz),
                reduce_only=data.reduceOnly,
                position_side=OkxEnumParser.parse_position_side(data.posSide),
            )
            self._msgbus.send(endpoint="okx.order", msg=order)

    def _handle_positions(self, raw: bytes):
        position_msg = self._decoder_ws_position_msg.decode(raw)
        self._log.debug(f"Position update: {str(position_msg)}")

        for data in position_msg.data:
            symbol = self._market_id[data.instId]

            side = data.posSide.parse_to_position_side()
            if side == PositionSide.LONG:
                signed_amount = Decimal(data.pos)
            elif side == PositionSide.SHORT:
                signed_amount = -Decimal(data.pos)
            elif side == PositionSide.FLAT:
                # one way mode, posSide always is 'net' from OKX ws msg, and pos amount is signed
                signed_amount = Decimal(data.pos)
                if signed_amount > 0:
                    side = PositionSide.LONG
                elif signed_amount < 0:
                    side = PositionSide.SHORT
                else:
                    side = None
            else:
                self._log.warning(f"Invalid position side: {side}")

            position = Position(
                symbol=symbol,
                exchange=self._exchange_id,
                side=side,
                signed_amount=signed_amount,
                entry_price=float(data.avgPx) if data.avgPx else 0,
                unrealized_pnl=float(data.upl) if data.upl else 0,
                realized_pnl=float(data.realizedPnl) if data.realizedPnl else 0,
            )

            self._cache._apply_position(position)

    def _handle_account(self, raw: bytes):
        account_msg: OkxWsAccountMsg = self._decoder_ws_account_msg.decode(raw)
        self._log.debug(f"Account update: {str(account_msg)}")

        for data in account_msg.data:
            balances = data.parse_to_balance()
            self._cache._apply_balance(self._account_type, balances)

    def _get_td_mode(self, market: OkxMarket):
        return OkxTdMode.CASH if market.spot else OkxTdMode.CROSS

    async def create_stop_loss_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        amount: Decimal,
        trigger_price: Decimal,
        trigger_type: TriggerType = TriggerType.LAST_PRICE,
        price: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        position_side: PositionSide | None = None,
        **kwargs,
    ) -> Order:
        pass

    async def create_take_profit_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        amount: Decimal,
        trigger_price: Decimal,
        trigger_type: TriggerType = TriggerType.LAST_PRICE,
        price: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        position_side: PositionSide | None = None,
        **kwargs,
    ) -> Order:
        pass

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        amount: Decimal,
        price: Decimal = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        position_side: PositionSide = None,
        **kwargs,
    ):
        if self._limiter:
            await self._limiter.acquire()

        market = self._market.get(symbol)
        if not market:
            raise ValueError(f"Symbol {symbol} formated wrongly, or not supported")
        symbol = market.id

        td_mode = kwargs.pop("td_mode", None)
        if not td_mode:
            td_mode = self._get_td_mode(market)

        params = {
            "inst_id": symbol,
            "td_mode": td_mode.value,
            "side": OkxEnumParser.to_okx_order_side(side).value,
            "ord_type": OkxEnumParser.to_okx_order_type(type, time_in_force).value,
            "sz": str(amount),
            "tag": "f50cdd72d3b6BCDE",
        }

        if type == OrderType.LIMIT:
            if not price:
                raise ValueError("Price is required for limit order")
            params["px"] = str(price)
        else:
            if market.spot:
                params["tgtCcy"] = "base_ccy"

        if position_side:
            params["posSide"] = OkxEnumParser.to_okx_position_side(position_side).value

        reduce_only = kwargs.pop("reduceOnly", False) or kwargs.pop(
            "reduce_only", False
        )
        if reduce_only:
            params["reduceOnly"] = True

        params.update(kwargs)

        try:
            res = await self._api_client.post_api_v5_trade_order(**params)
            res = res.data[0]
            order = Order(
                exchange=self._exchange_id,
                id=res.ordId,
                client_order_id=res.clOrdId,
                timestamp=int(res.ts),
                symbol=market.symbol,
                type=type,
                side=side,
                amount=amount,
                price=float(price) if price else None,
                time_in_force=time_in_force,
                position_side=position_side,
                status=OrderStatus.PENDING,
                filled=Decimal(0),
                remaining=amount,
            )
            return order
        except Exception as e:
            error_msg = f"{e.__class__.__name__}: {str(e)}"
            self._log.error(f"Error creating order: {error_msg} params: {str(params)}")
            order = Order(
                exchange=self._exchange_id,
                timestamp=self._clock.timestamp_ms(),
                symbol=market.symbol,
                type=type,
                side=side,
                amount=amount,
                price=float(price) if price else None,
                time_in_force=time_in_force,
                position_side=position_side,
                status=OrderStatus.FAILED,
                filled=Decimal(0),
                remaining=amount,
            )
            return order

    async def cancel_order(self, symbol: str, order_id: str, **kwargs):
        if self._limiter:
            await self._limiter.acquire()

        market = self._market.get(symbol)
        if not market:
            raise ValueError(f"Symbol {symbol} formated wrongly, or not supported")
        symbol = market.id

        params = {"inst_id": symbol, "ord_id": order_id, **kwargs}

        try:
            res = await self._api_client.post_api_v5_trade_cancel_order(**params)
            res = res.data[0]
            order = Order(
                exchange=self._exchange_id,
                id=res.ordId,
                client_order_id=res.clOrdId,
                timestamp=int(res.ts),
                symbol=symbol,
                status=OrderStatus.CANCELING,
            )
            return order
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            self._log.error(f"Error canceling order: {error_msg} params: {str(params)}")
            order = Order(
                exchange=self._exchange_id,
                timestamp=self._clock.timestamp_ms(),
                symbol=symbol,
                status=OrderStatus.CANCEL_FAILED,
            )
            return order

    async def disconnect(self):
        await super().disconnect()
        await self._api_client.close_session()
