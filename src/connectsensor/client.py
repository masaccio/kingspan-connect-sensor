"""Client for interacting with the Kingspan Connect Sensor."""

from __future__ import annotations

import json
import logging
from asyncio import get_running_loop
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Generic, NoReturn, Self, TypeVar, cast

import httpx
from zeep import AsyncClient as AsyncSoapClient
from zeep import Client as SoapClient
from zeep.helpers import serialize_object
from zeep.transports import AsyncTransport, Transport

from connectsensor.const import (
    API_BASE_URL,
    DEFAULT_API_TIMEOUT,
    DEFAULT_API_VERSION,
    HTTP_UNAUTHORIZED,
    SOAP_NS_PREFIX,
    TOKEN,
    WSDL_URL,
    APIVersion,
)
from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanInvalidResponseError,
    KingspanNoDataError,
    KingspanTimeoutError,
)
from connectsensor.models import HistoryPayload, LatestLevelPayload, LoginPayload
from connectsensor.tank import AsyncTank, Tank, _BaseTank

if TYPE_CHECKING:
    from types import TracebackType

    from connectsensor.analysis import TankHistoryPoint


_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("Using Kingspan API: %s", API_BASE_URL)

POST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}

TankT = TypeVar("TankT", bound=_BaseTank)


@dataclass(frozen=True, slots=True)
class _RequestSpec:
    """Protocol-agnostic description of an API request."""

    target: str  # SOAP method name (CONNECT_V1) or full URL (KNECT_V1)
    payload: dict[str, Any]


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

    def __init__(self, timeout: float = DEFAULT_API_TIMEOUT) -> None:
        """Initialize the HttpxTransport with a synchronous httpx.Client."""
        super().__init__()  # type: ignore[no-untyped-call]
        self.client: httpx.Client = httpx.Client(timeout=timeout)

    def close(self) -> None:
        """Close the synchronous HTTPX client."""
        self.client.close()

    def post(
        self,
        address: str,
        message: bytes | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        """Override the default `post` method to use `httpx.Client`."""
        return self.client.post(
            address,
            content=message,
            headers=headers,
        )


class _BaseClient(Generic[TankT]):
    """Base class for common helper functions."""

    def __init__(
        self,
        version: APIVersion = DEFAULT_API_VERSION,
        timeout: float = DEFAULT_API_TIMEOUT,
    ) -> None:
        _LOGGER.debug("Init API with version=%s", version.name)
        self._client: httpx.Client | httpx.AsyncClient | SoapClient | AsyncSoapClient | None = None
        self._version = version
        self._timeout = timeout
        self._username: str | None = None
        self._password: str | None = None
        self._user_id: str | None = None
        self._tanks: list[TankT] = []

    def redact_response(self, obj: Any) -> Any:  # noqa: ANN401
        """Redact sensitive values from request/response logs."""
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

    def check_response(self, response: object) -> dict[str, Any]:
        """Check the API response is well-formed or raise an exception."""
        try:
            if isinstance(response, httpx.Response):
                content: Any = response.json()
            else:
                content = _transform_soap_response(
                    serialize_object(response),  # type: ignore[no-untyped-call]
                )
        except ValueError as e:
            msg = f"Malformed response from API: cannot parse JSON ({e})"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanInvalidResponseError(msg) from e
        except Exception as e:
            # Catch-all for XML/Zeep serialization fatal errors
            msg = f"Unexpected error parsing response: {e}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanInvalidResponseError(msg) from e

        if not isinstance(content, dict):
            msg = f"Malformed response from API: expected dict, got {type(content).__name__}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanInvalidResponseError(msg)

        api_result = content.get("apiResult")
        if not isinstance(api_result, dict) or "code" not in api_result:
            msg = "Malformed response from API: cannot extract response/code"
            _LOGGER.debug(
                "API error: %s, content=%s",
                msg,
                self.redact_response(content),
            )
            raise KingspanInvalidResponseError(msg)

        if api_result["code"] != 0:
            msg = str(api_result.get("description") or "Unknown API error")

            if "Authentication Failed" in msg:
                raise KingspanInvalidCredentialsError(msg)
            if "no level data" in msg.lower():
                raise KingspanNoDataError(msg)

            raise KingspanAPIError(msg, KingspanErrorCode.CANNOT_CONNECT)

        _LOGGER.debug(
            "API request succeeded, content=%s",
            self.redact_response(content),
        )
        return content

    def handle_exception(self, exc: Exception) -> NoReturn:
        """Strictly trap and translate all HTTP and runtime exceptions."""
        if isinstance(exc, KingspanAPIError):
            raise exc

        if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
            msg = f"HTTP request timeout: {exc}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanTimeoutError(msg) from exc

        if isinstance(exc, httpx.HTTPError):
            msg = f"Network connection failed: {exc}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanAPIError(msg, KingspanErrorCode.CANNOT_CONNECT) from exc

        msg = f"Unexpected request failure: {exc}"
        _LOGGER.debug("API error: %s", msg)
        raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN) from exc

    def login_request(self, username: str, password: str) -> _RequestSpec:
        """Construct the API request spec for authentication."""
        self._username = username
        self._password = password
        if self._version == APIVersion.CONNECT_V1:
            return _RequestSpec(
                target="SoapMobileAPPAuthenicate_v3",
                payload={"emailaddress": self._username, "password": self._password},
            )

        return _RequestSpec(
            target=f"{API_BASE_URL}/v3/V3_SoapMobileApp/Authenticate_v3_Async",
            payload={"emailAddress": self._username, "password": self._password},
        )

    def login_response(self, response: httpx.Response | object) -> LoginPayload:
        """Process the login API response and store the user ID."""
        if isinstance(response, httpx.Response) and response.status_code == HTTP_UNAUTHORIZED:
            msg = "Invalid token authorization"
            raise KingspanInvalidCredentialsError(msg)

        data = self.check_response(response)
        parsed = LoginPayload.from_dict(data)
        self._user_id = parsed.user_id
        return parsed

    def get_latest_level_request(self, signalman_no: str) -> _RequestSpec:
        """Construct the API request spec for fetching the latest level."""
        payload: dict[str, Any] = {
            "userid": self._user_id,
            "password": self._password,
            "signalmanno": signalman_no,
            "culture": "en",
        }
        if self._version == APIVersion.CONNECT_V1:
            return _RequestSpec(
                target="SoapMobileAPPGetLatestLevel_v3",
                payload=payload,
            )

        return _RequestSpec(
            target=f"{API_BASE_URL}/v1/V1_SoapMobileApp/GetLatestLevel_v1_Async?culture=EN",
            payload=payload,
        )

    def get_history_request(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> _RequestSpec:
        """Build a call history request spec for all clients."""
        start_date_dt = (
            datetime.fromtimestamp(0)  # noqa: DTZ006
            if start_date is None
            else start_date
        )
        end_date_dt = datetime.now() if end_date is None else end_date  # noqa: DTZ005

        if self._version == APIVersion.CONNECT_V1:
            return _RequestSpec(
                target="SoapMobileAPPGetCallHistory_v1",
                payload={
                    "userid": self._user_id,
                    "password": self._password,
                    "signalmanno": signalman_no,
                    "startdate": start_date_dt.isoformat(),
                    "enddate": end_date_dt.isoformat(),
                },
            )

        return _RequestSpec(
            target=f"{API_BASE_URL}/v1/V1_SoapMobileApp/GetCallHistory_v1_Async",
            payload={
                "userIdPairWithSN": {
                    "userId": self._user_id,
                    "signalmanNo": signalman_no,
                    "password": self._password,
                },
                "startDate": start_date_dt.isoformat(),
                "endDate": end_date_dt.isoformat(),
            },
        )


class SensorClient(_BaseClient[Tank]):
    """Synchronous client for interacting with the Kingspan Connect Sensor API."""

    def __init__(
        self,
        version: APIVersion = DEFAULT_API_VERSION,
        timeout: float = DEFAULT_API_TIMEOUT,
    ) -> None:
        """Init for Synchronous client."""
        super().__init__(version, timeout)
        if self._version == APIVersion.CONNECT_V1:
            self._client = SoapClient(  # type: ignore[no-untyped-call]
                WSDL_URL,
                transport=HttpxTransport(timeout),
            )
            self._client.set_ns_prefix(None, SOAP_NS_PREFIX)  # type: ignore[no-untyped-call]
        else:
            self._client = httpx.Client(timeout=timeout)

    def __enter__(self) -> Self:
        """Enter the context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the context manager and close the client."""
        self.close()

    def close(self) -> None:
        """Close underlying connections."""
        if isinstance(self._client, httpx.Client):
            self._client.close()
        else:
            cast("SoapClient", self._client).transport.close()

    def _request(self, spec: _RequestSpec) -> object:
        try:
            if self._version == APIVersion.CONNECT_V1:
                soap_client = cast("SoapClient", self._client)
                method = getattr(soap_client.service, spec.target)
                return method(**spec.payload)

            http_client = cast("httpx.Client", self._client)
            return http_client.post(
                spec.target,
                headers=POST_HEADERS,
                content=json.dumps(spec.payload),
            )
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)

    def login(self, username: str, password: str) -> None:
        """Authenticate with the API and initialize tank list."""
        response = self._request(self.login_request(username, password))
        parsed = self.login_response(response)
        self._tanks = [Tank(self, sn) for sn in parsed.signalman_numbers]

    @property
    def tanks(self) -> list[Tank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    def _get_latest_level(self, signalman_no: str) -> LatestLevelPayload:
        """Tanks helper: get the latest level reading for a given tank."""
        response = self._request(self.get_latest_level_request(signalman_no))
        return LatestLevelPayload.from_dict(self.check_response(response))

    def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[TankHistoryPoint]:
        """Tanks helper: get the history data for a given tank."""
        response = self._request(
            self.get_history_request(signalman_no, start_date, end_date),
        )
        return HistoryPayload.from_dict(self.check_response(response)).points


class AsyncSensorClient(_BaseClient[AsyncTank]):
    """Asynchronous client for interacting with the Kingspan Connect Sensor API."""

    def __init__(
        self,
        version: APIVersion = DEFAULT_API_VERSION,
        client: httpx.AsyncClient | None = None,
        timeout: float = DEFAULT_API_TIMEOUT,
    ) -> None:
        """Initialize the async client with an optional injected httpx client."""
        super().__init__(version, timeout)
        self._has_injected_client = client is not None
        self._injected_client = client

    async def __aenter__(self) -> Self:
        """Enter the async context manager."""
        await self._init_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit the async context manager and close owned clients."""
        if isinstance(self._client, AsyncSoapClient):
            self._client.transport.wsdl_client.close()
            if not self._has_injected_client:
                await self._client.transport.client.aclose()
        elif not self._has_injected_client:
            client = cast("httpx.AsyncClient", self._client)
            await client.aclose()

    def _build_client(self) -> httpx.AsyncClient | AsyncSoapClient:
        """Build client in the executor to prevent blocking requests from httpx/zeep."""
        httpx_client = self._injected_client or httpx.AsyncClient(timeout=self._timeout)

        if self._version == APIVersion.CONNECT_V1:
            wsdl_client = httpx.Client(timeout=self._timeout)
            transport = AsyncTransport(client=httpx_client, wsdl_client=wsdl_client)  # type: ignore[no-untyped-call]
            soap_client = AsyncSoapClient(WSDL_URL, transport=transport)  # type: ignore[no-untyped-call]
            soap_client.set_ns_prefix(None, SOAP_NS_PREFIX)  # type: ignore[no-untyped-call]
            return soap_client

        return httpx_client

    async def _init_client(self) -> None:
        loop = get_running_loop()
        try:
            self._client = await loop.run_in_executor(None, self._build_client)
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)

    async def _request(self, spec: _RequestSpec) -> object:
        """Private wrapper for SOAP/HTTP calls."""
        try:
            if self._version == APIVersion.CONNECT_V1:
                soap_client = cast("AsyncSoapClient", self._client)
                method = getattr(soap_client.service, spec.target)
                return await method(**spec.payload)

            http_client = cast("httpx.AsyncClient", self._client)
            return await http_client.post(
                spec.target,
                headers=POST_HEADERS,
                content=json.dumps(spec.payload),
            )
        except Exception as e:  # noqa: BLE001 # pylint: disable=broad-exception-caught
            self.handle_exception(e)

    async def login(self, username: str, password: str) -> None:
        """Authenticate with the API and initialize tank list."""
        response = await self._request(self.login_request(username, password))
        parsed = self.login_response(response)
        self._tanks = [AsyncTank(self, sn) for sn in parsed.signalman_numbers]

    @property
    async def tanks(self) -> list[AsyncTank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    async def _get_latest_level(self, signalman_no: str) -> LatestLevelPayload:
        """Tanks helper: get the latest level reading for a given tank."""
        response = await self._request(self.get_latest_level_request(signalman_no))
        return LatestLevelPayload.from_dict(self.check_response(response))

    async def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[TankHistoryPoint]:
        """Tanks helper: get the history data for a given tank."""
        response = await self._request(
            self.get_history_request(signalman_no, start_date, end_date),
        )
        return HistoryPayload.from_dict(self.check_response(response)).points
