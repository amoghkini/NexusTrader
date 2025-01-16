import asyncio

from nexustrader.core import Strategy
from nexustrader.exchange.binance import (
    BinancePrivateConnector,
    BinanceExchangeManager,
    BinanceAccountType,
)
from nexustrader.constants import KEYS

BINANCE_API_KEY = KEYS["binance_future_testnet"]["API_KEY"]
BINANCE_API_SECRET = KEYS["binance_future_testnet"]["SECRET"]


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
        config = {
            "exchange_id": "binance",
            "apiKey": BINANCE_API_KEY,
            "secret": BINANCE_API_SECRET,
            "sandbox": True,
            "enableRateLimit": False,
        }

        exchange = BinanceExchangeManager(config)

        private_conn = BinancePrivateConnector(
            BinanceAccountType.USD_M_FUTURE_TESTNET,
            exchange,
        )

        demo = Demo()
        demo.add_private_connector(private_conn)

        await private_conn.connect()
        await demo.run()

    except asyncio.CancelledError:
        print("Websocket closed")
    finally:
        await private_conn.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
