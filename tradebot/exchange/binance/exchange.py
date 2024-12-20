import ccxt
import orjson
import msgspec
from typing import Any, Dict
from tradebot.base import ExchangeManager
from tradebot.exchange.binance.schema import BinanceMarket
from tradebot.schema import InstrumentId

class BinanceExchangeManager(ExchangeManager):
    api: ccxt.binance
    market: Dict[str, BinanceMarket] 
    market_id: Dict[str, str]
    
    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        config["exchange_id"] = config.get("exchange_id", "binance")
        super().__init__(config)
            
    def load_markets(self):
        market = self.api.load_markets()
        for symbol,mkt in market.items():
            try:
                mkt_json = orjson.dumps(mkt)
                mkt = msgspec.json.decode(mkt_json, type=BinanceMarket)
                
                if mkt.spot or mkt.future or mkt.linear or mkt.inverse:
                    symbol = self._parse_symbol(mkt, exchange_suffix="BINANCE")
                    mkt.symbol = symbol
                    self.market[symbol] = mkt
                    if mkt.type.value == "spot":
                        self.market_id[f"{mkt.id}_spot"] = symbol
                    elif mkt.linear:
                        self.market_id[f"{mkt.id}_linear"] = symbol
                    elif mkt.inverse:
                        self.market_id[f"{mkt.id}_inverse"] = symbol
                
            except Exception as e:
                print(f"Error: {e}, {symbol}, {mkt}")
                continue

def check():
    bnc = BinanceExchangeManager()
    market = bnc.market
    
    for symbol, mkt in market.items():
        instrument_id = InstrumentId.from_str(symbol)
        if mkt.subType:
            assert instrument_id.type == mkt.subType
        else:
            assert instrument_id.type == mkt.type
    
    print("All checks passed")

if __name__ == "__main__":
    check()
    
    
    
