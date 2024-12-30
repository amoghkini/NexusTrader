from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import ssl
import certifi
import orjson
import aiohttp
from tradebot.core.log import SpdLog
from tradebot.core.nautilius_core import LiveClock


class ApiClient(ABC):
    def __init__(
        self,
        api_key: str = None,
        secret: str = None,
        timeout: int = 10,
    ):
        self._api_key = api_key
        self._secret = secret
        self._timeout = timeout
        self._log = SpdLog.get_logger(type(self).__name__, level="DEBUG", flush=True)
        self._ssl_context = ssl.create_default_context(cafile=certifi.where())
        self._session: Optional[aiohttp.ClientSession] = None
        self._clock = LiveClock()

    def _init_session(self):
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            tcp_connector = aiohttp.TCPConnector(
                ssl=self._ssl_context, enable_cleanup_closed=True
            )
            self._session = aiohttp.ClientSession(
                connector=tcp_connector, json_serialize=orjson.dumps, timeout=timeout
            )

    async def close_session(self):
        if self._session:
            await self._session.close()
            self._session = None

    @abstractmethod
    def raise_error(self, raw: bytes, status: int, headers: Dict[str, Any]):
        raise NotImplementedError("Subclasses must implement this method.")
