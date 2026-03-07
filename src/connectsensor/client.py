"""Client for interacting with the Kingspan Connect Sensor."""

import json
import logging
from asyncio import get_running_loop
from collections.abc import Callable
from datetime import datetime

import httpx
from async_property import async_property
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


class HttpxTransport(Transport):
    """Custom Zeep transport using httpx.Client for synchronous HTTP requests."""

    def __init__(self) -> None:
        """Initialize the HttpxTransport with a synchronous httpx.Client."""
        super().__init__()
        self.client = httpx.Client()  # Synchronous HTTPX client

    def post(
        self,
        address: str,
        envelope: bytes | None,
        headers: dict,
    ) -> httpx.Response:
        """Override the default `post` method to use `httpx.Client`."""
        return self.client.post(
            address,
            data=envelope,  # type: ignore[reportOptionalMemberAccess]
            headers=headers,
        )


class _BaseClient:
    """Base class for common helper functions."""

    def __init__(self, version: APIVersion = DEFAULT_API_VERSION) -> None:
        """Initialize the base class."""
        _LOGGER.debug("Init API with version=%s", version.name)
        self._client = None
        self._version = version
        self._username = None
        self._password = None
        self._user_id = None
        self._tanks = []

    def redact_response(self, obj: APIResponse) -> APIResponse:
        """Redact values email and password from request/response."""
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                if key in ("emailAddress", "password", "apiUserID", "signalmanNo"):
                    new_dict[key] = "*redacted*"
                else:
                    new_dict[key] = self.redact_response(value)
            return new_dict

        if isinstance(obj, list):
            return [self.redact_response(item) for item in obj]

        return obj

    def check_response(self, response: object) -> APIResponse:  # noqa: C901
        """Check the API response is well-formed or raise an exception."""

        def transform_soap_response(obj: APIResponse) -> APIResponse:
            """Convert a SOAP response to the same structure as the JSON API."""

            def lower_first(s: str) -> str:
                if not s:
                    return s
                if s.startswith("API"):
                    return "api" + s[3:]
                return s[0].lower() + s[1:]

            if isinstance(obj, dict):
                result: dict = {}
                for k, v in obj.items():
                    if k in ("APILevel", "APITankInfo_V3", "APITankInfoItem"):
                        return transform_soap_response(v)
                    result[lower_first(k)] = transform_soap_response(v)
                return result

            if isinstance(obj, list):
                return [transform_soap_response(v) for v in obj]
            return obj

        if isinstance(response, httpx.Response):
            content = json.loads(response.content)
        else:
            content = transform_soap_response(serialize_object(response))

        if "apiResult" not in content or "code" not in content["apiResult"]:
            msg = "Malformed response from API: cannot extract response/code"
            _LOGGER.debug(
                "API error: %s, content=%s",
                msg,
                self.redact_response(content),
            )
            raise KingspanAPIError(msg)

        if content["apiResult"]["code"] != 0:
            msg = content["apiResult"]["description"]
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
        return content

    def handle_exception(self, exc: Exception) -> None:
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
        self._username = username
        self._password = password
        if self._version == APIVersion.CONNECT_V1:
            data = {"emailaddress": self._username, "password": self._password}
            return (self._client.service.SoapMobileAPPAuthenicate_v3, [], data)

        data = {"emailAddress": self._username, "password": self._password}
        return (
            self._client.post,
            [f"{API_BASE_URL}/v3/V3_SoapMobileApp/Authenticate_v3_Async"],
            {"headers": POST_HEADERS, "content": json.dumps(data)},
        )

    def login_response(
        self, response: httpx.Response | object, tank_type: type
    ) -> None:
        if (
            hasattr(response, "status_code")
            and response.status_code == HTTP_UNAUTHORIZED
        ):
            # JSON API for an invalid JWT
            msg = "Invalid token authorization"
            raise KingspanAPIError(msg)
        data = self.check_response(response)
        self._user_id = data["apiUserID"]
        for tank_info in data["tanks"]:
            self._tanks.append(tank_type(self, tank_info["signalmanNo"]))

    def get_latest_level_request(
        self,
        signalman_no: str,
    ) -> tuple[Callable, list, dict]:
        data = {
            "userid": self._user_id,
            "password": self._password,
            "signalmanno": signalman_no,
            "culture": "en",
        }

        if self._version == APIVersion.CONNECT_V1:
            return (self._client.service.SoapMobileAPPGetLatestLevel_v3, [], data)

        return (
            self._client.post,
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
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)  # noqa: DTZ006
        if end_date is None:
            end_date_dt = datetime.now()  # noqa: DTZ005

        if self._version == APIVersion.CONNECT_V1:
            data = {
                "userid": self._user_id,
                "password": self._password,
                "signalmanno": signalman_no,
                "startdate": start_date_dt.isoformat(),
                "enddate": end_date_dt.isoformat(),
            }
            return (self._client.service.SoapMobileAPPGetCallHistory_v1, [], data)

        data = {
            "userIdPairWithSN": {
                "userId": self._user_id,
                "signalmanNo": signalman_no,
                "password": self._password,
            },
            "startDate": start_date_dt.isoformat(),
            "endDate": end_date_dt.isoformat(),
        }
        return (
            self._client.post,
            [f"{API_BASE_URL}/v1/V1_SoapMobileApp/GetCallHistory_v1_Async"],
            {"headers": POST_HEADERS, "content": json.dumps(data)},
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

    def _request(self, func: Callable, *args: str | datetime | None) -> APIResponse:
        (func, req_args, req_kwargs) = func(*args)
        try:
            response = func(*req_args, **req_kwargs)
        except Exception as e:  # noqa: BLE001
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

    def _get_latest_level(self, signalman_no: str) -> dict:
        """Tanks helper: get the latest level reading for a given tank."""
        response = self._request(self.get_latest_level_request, signalman_no)
        return self.check_response(response)

    def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Tanks helper: get the history data for a given tank."""
        response = self._request(
            self.get_history_request,
            signalman_no,
            start_date,
            end_date,
        )
        new_response = self.check_response(response)
        return new_response["levels"]


class AsyncSensorClient(_BaseClient):
    """Asynchronous client for interacting with the Kingspan Connect Sensor API."""

    async def __aenter__(self) -> "AsyncSensorClient":
        """Enter the async context manager."""
        await self._init_client()
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb) -> None:  # noqa: ANN001
        """Exit the async context manager."""

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
        except Exception as e:  # noqa: BLE001
            self.handle_exception(e)

    async def _request(
        self, func: Callable, *args: str | datetime | None
    ) -> APIResponse:
        """Private wrapper for SOAP/HTTP calls."""
        (func, req_args, req_kwargs) = func(*args)
        try:
            response = await func(*req_args, **req_kwargs)
        except Exception as e:  # noqa: BLE001
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

    async def _get_latest_level(self, signalman_no: str) -> dict:
        """Tanks helper: get the latest level reading for a given tank."""
        response = await self._request(self.get_latest_level_request, signalman_no)
        return self.check_response(response)

    async def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Tanks helper: get the history data for a given tank."""
        response = await self._request(
            self.get_history_request,
            signalman_no,
            start_date,
            end_date,
        )
        new_response = self.check_response(response)
        return new_response["levels"]
