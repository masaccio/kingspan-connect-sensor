"""Client for interacting with the Kingspan Connect Sensor."""

from __future__ import annotations

import json
import logging
from asyncio import get_running_loop
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import TracebackType

import httpx
from typing_extensions import Self
from zeep import AsyncClient as AsyncSoapClient
from zeep import Client as SoapClient
from zeep.helpers import serialize_object
from zeep.transports import AsyncTransport, Transport

from connectsensor.const import (
    API_BASE_URL,
    DEFAULT_API_VERSION,
    HTTP_UNAUTHORIZED,
    SOAP_NS_PREFIX,
    TOKEN,
    WSDL_URL,
    APIResponse,
    APIResponseValue,
    APIVersion,
)
from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanInvalidCredentialsError,
    KingspanTimeoutError,
)
from connectsensor.tank import AsyncTank, Tank

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("Using Kingspan API: %s", API_BASE_URL)

POST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}


def _lower_first(s: str) -> str:
    """Lower the first character of a string, handling API prefixes."""
    if s.startswith("API"):
        return "api" + s[3:]
    return s[0].lower() + s[1:]


def _transform_soap_response(obj: Any) -> Any:  # noqa: ANN401
    """Convert a SOAP response to the same structure as the JSON API."""
    if isinstance(obj, dict):
        result: dict[str, Any] = {}
        for k, v in obj.items():
            if k in ("APILevel", "APITankInfo_V3", "APITankInfoItem"):
                return _transform_soap_response(v)
            result[_lower_first(k)] = _transform_soap_response(v)
        return result

    if isinstance(obj, list):
        return [_transform_soap_response(v) for v in obj]
    return obj


class HttpxTransport(Transport):
    """Custom Zeep transport using httpx.Client for synchronous HTTP requests."""

    def __init__(self) -> None:
        """Initialize the HttpxTransport with a synchronous httpx.Client."""
        super().__init__()
        self.client = httpx.Client()  # Synchronous HTTPX client

    def post(
        self,
        address: str,
        message: bytes | None,
        headers: dict,
    ) -> httpx.Response:
        """Override the default `post` method to use `httpx.Client`."""
        return self.client.post(
            address,
            content=message,
            headers=headers,
        )


class _BaseClient:
    """Base class for common helper functions."""

    def __init__(self, version: APIVersion = DEFAULT_API_VERSION) -> None:
        """Initialize the base class."""
        _LOGGER.debug("Init API with version=%s", version.name)
        self._client: httpx.Client | httpx.AsyncClient | SoapClient | AsyncSoapClient | None = None
        self._version = version
        self._username: str | None = None
        self._password: str | None = None
        self._user_id: str | None = None
        self._tanks: list[Any] = []

    def redact_response(self, obj: Any) -> Any:  # noqa: ANN401
        """Redact values email and password from request/response."""
        if isinstance(obj, dict):
            new_dict: dict[str, Any] = {}
            for key, value in obj.items():
                if key in ("emailAddress", "password", "apiUserID", "signalmanNo"):
                    new_dict[key] = "*redacted*"
                else:
                    new_dict[key] = self.redact_response(value)
            return new_dict

        if isinstance(obj, list):
            return [self.redact_response(item) for item in obj]

        return obj

    def check_response(self, response: object) -> APIResponse:
        """Check the API response is well-formed or raise an exception."""
        if isinstance(response, httpx.Response):
            content = json.loads(response.content)
        else:
            content = _transform_soap_response(serialize_object(response))

        if "apiResult" not in content or "code" not in content["apiResult"]:
            msg = "Malformed response from API: cannot extract response/code"
            _LOGGER.debug(
                "API error: %s, content=%s",
                msg,
                self.redact_response(content),
            )
            raise KingspanAPIError(msg)

        if content["apiResult"]["code"] != 0:
            msg = cast("str", content["apiResult"]["description"])
            _LOGGER.debug(
                "API error: %s, content=%s",
                msg,
                self.redact_response(content),
            )
            if "Authentication Failed" in msg:
                raise KingspanInvalidCredentialsError(msg)
            raise KingspanAPIError(content["apiResult"]["description"])

        _LOGGER.debug(
            "API request succeeded, content=%s",
            self.redact_response(content),
        )
        return cast("APIResponse", content)

    def handle_exception(self, exc: Exception) -> None:
        """Handle and translate HTTP and runtime exceptions."""
        if isinstance(exc, httpx.TimeoutException):
            msg = f"HTTP request timeout: {exc}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanTimeoutError(msg) from exc

        msg = f"HTTP request failed: {exc}"
        _LOGGER.debug("API error: %s", msg)
        raise KingspanAPIError(msg) from exc

    def login_request(
        self,
        username: str,
        password: str,
    ) -> tuple[Callable, list, dict]:
        """Construct the API request parameters for authentication."""
        self._username = username
        self._password = password
        client = cast("Any", self._client)
        if self._version == APIVersion.CONNECT_V1:
            data: dict[str, Any] = {"emailaddress": self._username, "password": self._password}
            return (client.service.SoapMobileAPPAuthenicate_v3, [], data)

        data = {"emailAddress": self._username, "password": self._password}
        return (
            client.post,
            [f"{API_BASE_URL}/v3/V3_SoapMobileApp/Authenticate_v3_Async"],
            {"headers": POST_HEADERS, "content": json.dumps(data)},
        )

    def login_response(
        self,
        response: httpx.Response | object,
        tank_type: type[Tank | AsyncTank],
    ) -> None:
        """Process the login API response and instantiate tank objects."""
        if hasattr(response, "status_code") and response.status_code == HTTP_UNAUTHORIZED:
            # JSON API for an invalid JWT
            msg = "Invalid token authorization"
            raise KingspanAPIError(msg)
        data = self.check_response(response)

        self._user_id = cast("str", data["apiUserID"])
        tanks_list = cast("list[dict[str, Any]]", data["tanks"])
        for tank_info in tanks_list:
            self._tanks.append(tank_type(self, cast("str", tank_info["signalmanNo"])))

    def get_latest_level_request(
        self,
        signalman_no: str,
    ) -> tuple[Callable, list, dict]:
        """Construct the API request parameters for fetching the latest level."""
        data: dict[str, Any] = {
            "userid": self._user_id,
            "password": self._password,
            "signalmanno": signalman_no,
            "culture": "en",
        }
        client = cast("Any", self._client)
        if self._version == APIVersion.CONNECT_V1:
            return (client.service.SoapMobileAPPGetLatestLevel_v3, [], data)

        return (
            client.post,
            [f"{API_BASE_URL}/v1/V1_SoapMobileApp/GetLatestLevel_v1_Async?culture=EN"],
            {"headers": POST_HEADERS, "content": json.dumps(data)},
        )

    def get_history_request(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[Callable, list, dict]:
        """Build a call history request for all clients."""
        start_date_dt = (
            datetime.fromtimestamp(0)  # noqa: DTZ006
            if start_date is None
            else start_date
        )
        end_date_dt = datetime.now() if end_date is None else end_date  # noqa: DTZ005

        client = cast("Any", self._client)
        if self._version == APIVersion.CONNECT_V1:
            data_v1: dict[str, Any] = {
                "userid": self._user_id,
                "password": self._password,
                "signalmanno": signalman_no,
                "startdate": start_date_dt.isoformat(),
                "enddate": end_date_dt.isoformat(),
            }
            return (client.service.SoapMobileAPPGetCallHistory_v1, [], data_v1)

        data_v3: dict[str, Any] = {
            "userIdPairWithSN": {
                "userId": self._user_id,
                "signalmanNo": signalman_no,
                "password": self._password,
            },
            "startDate": start_date_dt.isoformat(),
            "endDate": end_date_dt.isoformat(),
        }
        return (
            client.post,
            [f"{API_BASE_URL}/v1/V1_SoapMobileApp/GetCallHistory_v1_Async"],
            {"headers": POST_HEADERS, "content": json.dumps(data_v3)},
        )


class SensorClient(_BaseClient):
    """Synchronous client for interacting with the Kingspan Connect Sensor API."""

    def __init__(self, version: APIVersion = DEFAULT_API_VERSION) -> None:
        """Init for Synchronous client."""
        super().__init__(version)
        if self._version == APIVersion.CONNECT_V1:
            self._client = SoapClient(WSDL_URL, transport=HttpxTransport())
            self._client.set_ns_prefix(None, SOAP_NS_PREFIX)
        else:
            self._client = httpx.Client()

    def _request(self, func: Callable, *args: str | datetime | None) -> Any:  # noqa: ANN401
        func, req_args, req_kwargs = func(*args)
        try:
            response = func(*req_args, **req_kwargs)
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)
        return response

    def login(self, username: str, password: str) -> None:
        """Authenticate with the API and initialize tank list."""
        response = self._request(self.login_request, username, password)
        self.login_response(response, Tank)

    @property
    def tanks(self) -> list[Tank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    def _get_latest_level(self, signalman_no: str) -> APIResponse:
        """Tanks helper: get the latest level reading for a given tank."""
        response = self._request(self.get_latest_level_request, signalman_no)
        return self.check_response(response)

    def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, APIResponseValue]]:
        """Tanks helper: get the history data for a given tank."""
        response = self._request(
            self.get_history_request,
            signalman_no,
            start_date,
            end_date,
        )
        new_response = self.check_response(response)
        return cast("list[dict[str, APIResponseValue]]", new_response["levels"])


class AsyncSensorClient(_BaseClient):
    """Asynchronous client for interacting with the Kingspan Connect Sensor API."""

    def __init__(
        self,
        version: APIVersion = DEFAULT_API_VERSION,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize the async client with an optional injected httpx client."""
        super().__init__(version)
        self._injected_client = client is not None
        if client is not None:
            self._client = client

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        if self._client is None:
            await self._init_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager and close the client if we created it."""
        if not self._injected_client and hasattr(self._client, "aclose"):
            await cast("Any", self._client).aclose()

    async def _init_client(self) -> None:
        # httpx.AsyncClient loads certificates in a blocking manner which is flagged
        # by Home Assistant, so we run in its own thread once on the first request.
        def _build_client() -> httpx.AsyncClient | AsyncSoapClient:
            if self._version == APIVersion.CONNECT_V1:
                wsdl_client = httpx.Client()
                httpx_client = httpx.AsyncClient()
                transport = AsyncTransport(client=httpx_client, wsdl_client=wsdl_client)
                client = AsyncSoapClient(WSDL_URL, transport=transport)
                client.set_ns_prefix(None, SOAP_NS_PREFIX)
                return client

            return httpx.AsyncClient()

        loop = get_running_loop()
        try:
            self._client = await loop.run_in_executor(None, _build_client)
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)

    async def _request(
        self,
        func: Callable,
        *args: str | datetime | None,
    ) -> Any:  # noqa: ANN401
        """Private wrapper for SOAP/HTTP calls."""
        func, req_args, req_kwargs = func(*args)
        try:
            response = await func(*req_args, **req_kwargs)
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)
        return response

    async def login(self, username: str, password: str) -> None:
        """Authenticate with the API and initialize tank list."""
        response = await self._request(self.login_request, username, password)
        self.login_response(response, AsyncTank)

    @property
    async def tanks(self) -> list[AsyncTank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    async def _get_latest_level(self, signalman_no: str) -> APIResponse:
        """Tanks helper: get the latest level reading for a given tank."""
        response = await self._request(self.get_latest_level_request, signalman_no)
        return self.check_response(response)

    async def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, APIResponseValue]]:
        """Tanks helper: get the history data for a given tank."""
        response = await self._request(
            self.get_history_request,
            signalman_no,
            start_date,
            end_date,
        )
        new_response = self.check_response(response)
        return cast("list[dict[str, APIResponseValue]]", new_response["levels"])
