import httpx
from async_property import async_property
from connectsensor.const import (
    APIRequest as APIRequest,
    APIResponse as APIResponse,
    API_BASE_URL as API_BASE_URL,
    HTTP_UNAUTHORIZED as HTTP_UNAUTHORIZED,
    TOKEN as TOKEN,
)
from connectsensor.exceptions import (
    KingspanAPIError as KingspanAPIError,
    KingspanInvalidCredentialsError as KingspanInvalidCredentialsError,
    KingspanTimeoutError as KingspanTimeoutError,
)
from connectsensor.tank import AsyncTank as AsyncTank, Tank as Tank
from datetime import datetime

class _BaseClient:
    def __init__(self) -> None: ...
    def redact(self, obj: APIResponse) -> APIResponse: ...
    def build_request(
        self, endpoint: str, data: dict[str, str | list | dict]
    ) -> tuple: ...
    def check_payload(self, response: httpx.Response) -> APIResponse: ...
    def httpx_exception(self, exc: Exception) -> None: ...
    def get_history_request(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[str, APIRequest]: ...

class SensorClient(_BaseClient):
    def __init__(self) -> None: ...
    def login(self, username: str, password: str) -> None: ...
    @property
    def tanks(self) -> list[Tank]: ...

class AsyncSensorClient(_BaseClient):
    async def __aenter__(self) -> AsyncSensorClient: ...
    async def __aexit__(self, exc_t, exc_v, exc_tb) -> None: ...
    async def login(self, username: str, password: str) -> None: ...
    @async_property
    async def tanks(self) -> list[AsyncTank]: ...
