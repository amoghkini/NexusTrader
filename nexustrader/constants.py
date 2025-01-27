import os
import sys
from typing import Literal, Dict, List
from enum import Enum
from dynaconf import Dynaconf


def is_sphinx_build():
    return "sphinx" in sys.modules


if not os.path.exists(".keys/"):
    os.makedirs(".keys/")
if not os.path.exists(".keys/.secrets.toml") and not is_sphinx_build():
    raise FileNotFoundError(
        "Config file not found, please create a config file at .keys/.secrets.toml"
    )


settings = Dynaconf(
    envvar_prefix="NEXUS",
    settings_files=[".keys/settings.toml", ".keys/.secrets.toml"],
    load_dotenv=True,
)


def get_redis_config(in_docker: bool = False):
    try:
        if in_docker:
            return {
                "host": "redis",
                "db": settings.REDIS_DB,
                "password": settings.REDIS_PASSWORD,
            }

        return {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB,
            "password": settings.REDIS_PASSWORD,
        }
    except Exception as e:
        raise ValueError(f"Failed to get Redis password: {e}")


IntervalType = Literal[
    "1s",
    "1m",
    "3m",
    "5m",
    "15m",
    "30m",
    "1h",
    "2h",
    "4h",
    "6h",
    "8h",
    "12h",
    "1d",
    "3d",
    "1w",
    "1M",
]


class SubmitType(Enum):
    CREATE = 0
    CANCEL = 1
    TWAP = 2
    CANCEL_TWAP = 3
    VWAP = 4
    CANCEL_VWAP = 5


class EventType(Enum):
    BOOKL1 = 0
    TRADE = 1
    KLINE = 2
    MARK_PRICE = 3
    FUNDING_RATE = 4
    INDEX_PRICE = 5


class AlgoOrderStatus(Enum):
    RUNNING = "RUNNING"
    CANCELING = "CANCELING"
    FINISHED = "FINISHED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class OrderStatus(Enum):
    # LOCAL
    INITIALIZED = "INITIALIZED"
    FAILED = "FAILED"
    CANCEL_FAILED = "CANCEL_FAILED"

    # IN-FLOW
    PENDING = "PENDING"
    CANCELING = "CANCELING"

    # OPEN
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"

    # CLOSED
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class ExchangeType(Enum):
    BINANCE = "binance"
    OKX = "okx"
    BYBIT = "bybit"


class BinanceAccountType(Enum):
    SPOT = "SPOT"
    MARGIN = "MARGIN"
    ISOLATED_MARGIN = "ISOLATED_MARGIN"
    USD_M_FUTURE = "USD_M_FUTURE"
    COIN_M_FUTURE = "COIN_M_FUTURE"
    PORTFOLIO_MARGIN = "PORTFOLIO_MARGIN"
    SPOT_TESTNET = "SPOT_TESTNET"
    USD_M_FUTURE_TESTNET = "USD_M_FUTURE_TESTNET"
    COIN_M_FUTURE_TESTNET = "COIN_M_FUTURE_TESTNET"


class AccountType(Enum):
    pass


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class InstrumentType(Enum):
    SPOT = "spot"
    MARGIN = "margin"
    FUTURE = "future"
    OPTION = "option"
    SWAP = "swap"
    LINEAR = "linear"
    INVERSE = "inverse"


class OptionType(Enum):
    CALL = "call"
    PUT = "put"


STATUS_TRANSITIONS: Dict[OrderStatus, List[OrderStatus]] = {
    OrderStatus.PENDING: [
        OrderStatus.CANCELED,
        OrderStatus.CANCELING,
        OrderStatus.ACCEPTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCELED,
        OrderStatus.FILLED,
        OrderStatus.CANCEL_FAILED,
    ],
    OrderStatus.CANCELING: [
        OrderStatus.CANCELED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
    ],
    OrderStatus.ACCEPTED: [
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELING,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCEL_FAILED,
    ],
    OrderStatus.PARTIALLY_FILLED: [
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELING,
        OrderStatus.CANCELED,
        OrderStatus.EXPIRED,
        OrderStatus.CANCEL_FAILED,
    ],
    OrderStatus.FILLED: [],
    OrderStatus.CANCELED: [],
    OrderStatus.EXPIRED: [],
    OrderStatus.FAILED: [],
}


class DataType(Enum):
    BOOKL1 = "bookl1"
    BOOKL2 = "bookl2"
    TRADE = "trade"
    KLINE = "kline"
    MARK_PRICE = "mark_price"
    FUNDING_RATE = "funding_rate"
    INDEX_PRICE = "index_price"


class StorageBackend(Enum):
    REDIS = "redis"
    SQLITE = "sqlite"
