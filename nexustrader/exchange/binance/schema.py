import msgspec
from decimal import Decimal
from typing import Any, Dict, List
from nexustrader.schema import BaseMarket, Balance
from nexustrader.constants import OrderSide, TimeInForce
from nexustrader.exchange.binance.constants import (
    BinanceAccountEventReasonType,
    BinanceOrderStatus,
    BinanceOrderType,
    BinancePositionSide,
    BinanceWsEventType,
    BinanceKlineInterval,
    BinanceUserDataStreamWsEventType,
    BinanceOrderSide,
    BinanceTimeInForce,
    BinanceExecutionType,
    BinanceFuturesWorkingType,
    BinanceBusinessUnit,
)


class BinanceFuturesBalanceInfo(msgspec.Struct, frozen=True):

    asset: str  # asset name
    walletBalance: str  # wallet balance
    unrealizedProfit: str  # unrealized profit
    marginBalance: str  # margin balance
    maintMargin: str  # maintenance margin required
    initialMargin: str  # total initial margin required with current mark price
    positionInitialMargin: str  # initial margin required for positions with current mark price
    openOrderInitialMargin: str  # initial margin required for open orders with current mark price
    crossWalletBalance: str  # crossed wallet balance
    crossUnPnl: str  # unrealized profit of crossed positions
    availableBalance: str  # available balance
    maxWithdrawAmount: str  # maximum amount for transfer out
    # whether the asset can be used as margin in Multi - Assets mode
    marginAvailable: bool | None = None
    updateTime: int | None = None  # last update time
    
    def parse_to_balance(self) -> Balance:
        free = Decimal(self.availableBalance)
        locked = Decimal(self.marginBalance) - free
        return Balance(
            asset=self.asset,
            free=free,
            locked=locked,
        )

class BinanceFuturesPositionInfo(msgspec.Struct, kw_only=True):
    symbol: str # symbol name
    initialMargin: str # initial margin required with current mark price
    maintMargin: str # maintenance margin required
    unrealizedProfit: str # unrealized profit
    positionInitialMargin: str # initial margin required for positions with current mark price
    openOrderInitialMargin: str # initial margin required for open orders with current mark price
    leverage: str # current initial leverage
    isolated: bool # if the position is isolated
    entryPrice: str # average entry price
    maxNotional: str | None = None # maximum available notional with current leverage
    bidNotional: str | None = None # bids notional, ignore
    askNotional: str | None = None # ask notional, ignore
    positionSide: BinancePositionSide # position side
    positionAmt: str # position amount
    updateTime: int
    breakEvenPrice: str | None = None # break-even price
    maxQty: str | None = None # maximum quantity of base asset

class BinanceFuturesAccountInfo(msgspec.Struct, kw_only=True):

    feeTier: int  # account commission tier
    canTrade: bool  # if can trade
    canDeposit: bool  # if can transfer in asset
    canWithdraw: bool  # if can transfer out asset
    updateTime: int
    totalInitialMargin: str | None = (
        None  # total initial margin required with current mark price (useless with isolated positions), only for USDT
    )
    totalMaintMargin: str | None = None  # total maintenance margin required, only for USDT asset
    totalWalletBalance: str | None = None  # total wallet balance, only for USDT asset
    totalUnrealizedProfit: str | None = None  # total unrealized profit, only for USDT asset
    totalMarginBalance: str | None = None  # total margin balance, only for USDT asset
    # initial margin required for positions with current mark price, only for USDT asset
    totalPositionInitialMargin: str | None = None
    # initial margin required for open orders with current mark price, only for USDT asset
    totalOpenOrderInitialMargin: str | None = None
    totalCrossWalletBalance: str | None = None  # crossed wallet balance, only for USDT asset
    # unrealized profit of crossed positions, only for USDT asset
    totalCrossUnPnl: str | None = None
    availableBalance: str | None = None  # available balance, only for USDT asset
    maxWithdrawAmount: str | None = None  # maximum amount for transfer out, only for USDT asset
    assets: list[BinanceFuturesBalanceInfo]
    positions: list[BinanceFuturesPositionInfo]

    def parse_to_balances(self) -> List[Balance]:
        return [balance.parse_to_balance() for balance in self.assets]

class BinanceSpotBalanceInfo(msgspec.Struct):
    asset: str
    free: str
    locked: str

    def parse_to_balance(self) -> Balance:
        return Balance(
            asset=self.asset,
            free=Decimal(self.free),
            locked=Decimal(self.locked),
        )

class BinanceSpotAccountInfo(msgspec.Struct, frozen=True):
    makerCommission: int
    takerCommission: int
    buyerCommission: int
    sellerCommission: int
    canTrade: bool
    canWithdraw: bool
    canDeposit: bool
    updateTime: int
    accountType: str
    balances: list[BinanceSpotBalanceInfo]
    permissions: list[str]

    def parse_to_balances(self) -> List[Balance]:
        return [balance.parse_to_balance() for balance in self.balances]

class BinanceSpotOrderUpdateMsg(msgspec.Struct, kw_only=True):
    e: BinanceUserDataStreamWsEventType
    E: int  # Event time
    s: str  # Symbol
    c: str  # Client order ID
    S: BinanceOrderSide 
    o: BinanceOrderType
    f: BinanceTimeInForce
    q: str  # Original Quantity
    p: str  # Original Price
    P: str  # Stop price
    F: str  # Iceberg quantity
    g: int  # Order list ID
    C: str  # Original client order ID; This is the ID of the order being canceled
    x: BinanceExecutionType
    X: BinanceOrderStatus
    r: str  # Order reject reason; will be an error code
    i: int  # Order ID
    l: str  # Order Last Filled Quantity # noqa
    z: str  # Order Filled Accumulated Quantity
    L: str  # Last Filled Price
    n: str | None = None  # Commission, will not push if no commission
    N: str | None = None  # Commission Asset, will not push if no commission
    T: int  # Order Trade Time
    t: int  # Trade ID
    I: int  # Ignore # noqa
    w: bool  # Is the order on the book?
    m: bool  # Is trade the maker side
    M: bool  # Ignore 
    O: int  # Order creation time # noqa
    Z: str  # Cumulative quote asset transacted quantity
    Y: str  # Last quote asset transacted quantity (i.e. lastPrice * lastQty)
    Q: str  # Quote Order Qty

class BinanceFuturesOrderData(msgspec.Struct, kw_only=True):
    s: str  # Symbol
    c: str  # Client Order ID
    S: BinanceOrderSide
    o: BinanceOrderType
    f: BinanceTimeInForce
    q: str  # Original Quantity
    p: str  # Original Price
    ap: str  # Average Price
    sp: str | None = None  # Stop Price. Ignore with TRAILING_STOP_MARKET order
    x: BinanceExecutionType
    X: BinanceOrderStatus
    i: int  # Order ID
    l: str  # Order Last Filled Quantity # noqa
    z: str  # Order Filled Accumulated Quantity
    L: str  # Last Filled Price
    N: str | None = None  # Commission Asset, will not push if no commission
    n: str | None = None  # Commission, will not push if no commission
    T: int  # Order Trade Time
    t: int  # Trade ID
    b: str  # Bids Notional
    a: str  # Ask Notional
    m: bool  # Is trade the maker side
    R: bool  # Is reduce only
    wt: BinanceFuturesWorkingType
    ot: BinanceOrderType
    ps: BinancePositionSide
    cp: bool | None = None  # If Close-All, pushed with conditional order
    AP: str | None = (
        None  # Activation Price, only pushed with TRAILING_STOP_MARKET order
    )
    cr: str | None = None  # Callback Rate, only pushed with TRAILING_STOP_MARKET order
    pP: bool  # ignore
    si: int  # ignore
    ss: int  # ignore
    rp: str  # Realized Profit of the trade
    gtd: int  # TIF GTD order auto cancel time


class BinanceFuturesOrderUpdateMsg(msgspec.Struct, kw_only = True):
    """
    WebSocket message for Binance Futures Order Update events.
    """
    e: BinanceUserDataStreamWsEventType
    E: int  # Event Time
    T: int  # Transaction Time
    fs: BinanceBusinessUnit | None = None  # Event business unit. 'UM' for USDS-M futures and 'CM' for COIN-M futures 
    o: BinanceFuturesOrderData


class BinanceMarkPrice(msgspec.Struct):
    e: BinanceWsEventType
    E: int
    s: str
    p: str
    i: str
    P: str
    r: str
    T: int


class BinanceKlineData(msgspec.Struct):
    t: int  # Kline start time
    T: int  # Kline close time
    s: str  # Symbol
    i: BinanceKlineInterval  # Interval
    f: int  # First trade ID
    L: int  # Last trade ID
    o: str  # Open price
    c: str  # Close price
    h: str  # High price
    l: str  # Low price # noqa
    v: str  # Base asset volume
    n: int  # Number of trades
    x: bool  # Is this kline closed?
    q: str  # Quote asset volume
    V: str  # Taker buy base asset volume
    Q: str  # Taker buy quote asset volume
    B: str  # Ignore


class BinanceKline(msgspec.Struct):
    e: BinanceWsEventType
    E: int
    s: str
    k: BinanceKlineData


class BinanceTradeData(msgspec.Struct):
    e: BinanceWsEventType
    E: int
    s: str
    t: int
    p: str
    q: str
    T: int


class BinanceSpotBookTicker(msgspec.Struct):
    """
      {
        "u":400900217,     // order book updateId
        "s":"BNBUSDT",     // symbol
        "b":"25.35190000", // best bid price
        "B":"31.21000000", // best bid qty
        "a":"25.36520000", // best ask price
        "A":"40.66000000"  // best ask qty
    }
    """
    u: int
    s: str
    b: str
    B: str
    a: str
    A: str


class BinanceFuturesBookTicker(msgspec.Struct):
    e: BinanceWsEventType
    u: int
    E: int
    T: int
    s: str
    b: str
    B: str
    a: str
    A: str


class BinanceWsMessageGeneral(msgspec.Struct):
    e: BinanceWsEventType | None = None
    u: int | None = None


class BinanceUserDataStreamMsg(msgspec.Struct):
    e: BinanceUserDataStreamWsEventType | None = None


class BinanceListenKey(msgspec.Struct):
    listenKey: str


class BinanceUserTrade(msgspec.Struct, frozen=True):
    commission: str
    commissionAsset: str
    price: str
    qty: str

    # Parameters not present in 'fills' list (see FULL response of BinanceOrder)
    symbol: str | None = None
    id: int | None = None
    orderId: int | None = None
    time: int | None = None
    quoteQty: str | None = None  # SPOT/MARGIN & USD-M FUTURES only

    # Parameters in SPOT/MARGIN only:
    orderListId: int | None = None  # unless OCO, the value will always be -1
    isBuyer: bool | None = None
    isMaker: bool | None = None
    isBestMatch: bool | None = None
    tradeId: int | None = None  # only in BinanceOrder FULL response

    # Parameters in FUTURES only:
    buyer: bool | None = None
    maker: bool | None = None
    realizedPnl: str | None = None
    side: OrderSide | None = None
    positionSide: str | None = None
    baseQty: str | None = None  # COIN-M FUTURES only
    pair: str | None = None  # COIN-M FUTURES only


class BinanceOrder(msgspec.Struct, frozen=True):
    symbol: str
    orderId: int
    clientOrderId: str

    # Parameters not in ACK response:
    price: str | None = None
    origQty: str | None = None
    executedQty: str | None = None
    status: BinanceOrderStatus | None = None
    timeInForce: TimeInForce | None = None
    goodTillDate: int | None = None
    type: BinanceOrderType | None = None
    side: OrderSide | None = None
    stopPrice: str | None = (
        None  # please ignore when order type is TRAILING_STOP_MARKET
    )
    time: int | None = None
    updateTime: int | None = None

    # Parameters in SPOT/MARGIN only:
    orderListId: int | None = None  # Unless OCO, the value will always be -1
    cumulativeQuoteQty: str | None = None  # cumulative quote qty
    icebergQty: str | None = None
    isWorking: bool | None = None
    workingTime: int | None = None
    origQuoteOrderQty: str | None = None
    selfTradePreventionMode: str | None = None
    transactTime: int | None = None  # POST & DELETE methods only
    fills: list[BinanceUserTrade] | None = None  # FULL response only

    # Parameters in FUTURES only:
    avgPrice: str | None = None
    origType: BinanceOrderType | None = None
    reduceOnly: bool | None = None
    positionSide: BinancePositionSide | None = None
    closePosition: bool | None = None
    activatePrice: str | None = (
        None  # activation price, only for TRAILING_STOP_MARKET order
    )
    priceRate: str | None = None  # callback rate, only for TRAILING_STOP_MARKET order
    workingType: str | None = None
    priceProtect: bool | None = None  # if conditional order trigger is protected
    cumQuote: str | None = None  # USD-M FUTURES only
    cumBase: str | None = None  # COIN-M FUTURES only
    pair: str | None = None  # COIN-M FUTURES only


class BinanceMarketInfo(msgspec.Struct):
    symbol: str = None
    status: str = None
    baseAsset: str = None
    baseAssetPrecision: str | int = None
    quoteAsset: str = None
    quotePrecision: str | int = None
    quoteAssetPrecision: str | int = None
    baseCommissionPrecision: str | int = None
    quoteCommissionPrecision: str | int = None
    orderTypes: List[BinanceOrderType] = None
    icebergAllowed: bool = None
    ocoAllowed: bool = None
    otoAllowed: bool = None
    quoteOrderQtyMarketAllowed: bool = None
    allowTrailingStop: bool = None
    cancelReplaceAllowed: bool = None
    isSpotTradingAllowed: bool = None
    isMarginTradingAllowed: bool = None
    filters: List[Dict[str, Any]] = None
    permissions: List[str] = None
    permissionSets: List[List[str]] = None
    defaultSelfTradePreventionMode: str = None
    allowedSelfTradePreventionModes: List[str] = None


class BinanceMarket(BaseMarket):
    info: BinanceMarketInfo
    feeSide: str


class BinanceAccountBalanceData(msgspec.Struct):
    a: str
    wb: str
    cw: str
    bc: str

class BinanceAccountPositionData(msgspec.Struct, kw_only=True):
    s: str
    pa: str # position amount
    ep: str # entry price
    bep: str # breakeven price
    cr: str # (Pre-fee) Accumulated Realized
    up: str # Unrealized PnL
    mt: str | None = None # margin type (if isolated position)
    iw: str | None = None # isolated wallet (if isolated position)
    ps: BinancePositionSide

class BinanceAccountUpdateData(msgspec.Struct, kw_only=True):
    m: BinanceAccountEventReasonType
    B: list[BinanceAccountBalanceData]
    P: list[BinanceAccountPositionData]

class BinanceAccountUpdateMsg(msgspec.Struct, kw_only=True):
    e: BinanceUserDataStreamWsEventType
    E: int
    T: int
    fs: BinanceBusinessUnit | None = None
    a: BinanceAccountUpdateData
