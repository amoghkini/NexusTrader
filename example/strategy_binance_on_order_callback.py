import asyncio

from tradebot.strategy import Strategy
from tradebot.exchange.binance import (
    BinancePrivateConnector,
    BinanceExchangeManager,
    BinanceAccountType,
)
from tradebot.constants import CONFIG

BINANCE_API_KEY = CONFIG["binance_future_testnet"]["API_KEY"]
BINANCE_API_SECRET = CONFIG["binance_future_testnet"]["SECRET"]



class Demo(Strategy):
    def on_new_order(self, order):
        print(f"New order: {order}")
    
    def on_partially_filled_order(self, order):
        print(f"Partially filled order: {order}")
    
    def on_filled_order(self, order):
        print(f"Filled order: {order}")
    
    def on_canceled_order(self, order):
        print(f"Canceled order: {order}")


async def main():
    try:
        exchange = BinanceExchangeManager({"exchange_id": "binance"})
        await exchange.load_markets()

        private_conn = BinancePrivateConnector(
            BinanceAccountType.USD_M_FUTURE_TESTNET,
            BINANCE_API_KEY,
            BINANCE_API_SECRET,
            exchange.market,
            exchange.market_id,
        )
        
        demo = Demo()
        demo.add_private_connector(private_conn)

        await private_conn.connect()
        await demo.run()

    except asyncio.CancelledError:
        print("Websocket closed")
    finally:
        await exchange.close()
        await private_conn.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
