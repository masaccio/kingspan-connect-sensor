"""Client for interacting with the Kingspan Connect Sensor."""

import json
import logging
from asyncio import get_running_loop
from datetime import datetime

import httpx
from async_property import async_property

from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanInvalidCredentials,
    KingspanTimeoutError,
)
from connectsensor.tank import AsyncTank, Tank

# API is HTTP and sends the username and password in the clear
API_SERVER = "sensorapi.connectsensor.com"
API_PORT = 8087
API_BASE_URL = f"http://{API_SERVER}:{API_PORT}"

# The JWT appears to be hard-coded into the application rather than securely returned
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJUaGVNb2JpbGVBcHAiLCJyb2xlIjoiVGhlTW9iaWxlQXBwIiwiZXhwIjoxNzg2ODk4NTM3LCJpc3MiOiJTZW5zb3JBUEkgQXV0aFNlcnZlciIsImF1ZCI6IlNlbnNvckFQSSBVc2VycyJ9.PW-NP46vP9pP5Da87KIzsN6ZWIA3vOI4XbqxHWVuTOY"  # noqa: E501, S105

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("Using Kingspan API: %s", API_BASE_URL)


class _BaseClient:
    """Base class for common helper functions."""

    def __init__(self) -> None:
        """Initialize the base class."""
        self._client = None
        self._username = None
        self._password = None
        self._user_id = None
        self._tanks = []

    def redact(self, obj: dict[str, str | list | dict]) -> dict[str, str | list | dict]:
        """Redact values email and password from request/response."""
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                if key in ("emailAddress", "password", "apiUserID", "signalmanNo"):
                    new_dict[key] = "*redacted*"
                else:
                    new_dict[key] = self.redact(value)
            return new_dict

        if isinstance(obj, list):
            return [self.redact(item) for item in obj]

        return obj

    def build_request(self, endpoint: str, data: dict[str, str | list | dict]) -> tuple:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {TOKEN}",
        }
        url = f"{API_BASE_URL}{endpoint}"
        _LOGGER.debug(
            "API request %s, headers=%s, content=%s", url, headers, self.redact(data),
        )
        return (url, headers, json.dumps(data))

    def check_payload(self, response: httpx.Response) -> dict[str, str | list | dict]:
        payload = json.loads(response.content)
        if "apiResult" not in payload or "code" not in payload["apiResult"]:
            msg = "Malformed response from API: cannot extract response/code"
            _LOGGER.debug("API error: %s, payload=%s", msg, self.redact(payload))
            raise KingspanAPIError(msg)

        if payload["apiResult"]["code"] != 0:
            msg = payload["apiResult"]["description"]
            _LOGGER.debug("API error: %s, payload=%s", msg, self.redact(payload))
            if "Authentication Failed" in msg:
                raise KingspanInvalidCredentials(msg)
            raise KingspanAPIError(payload["apiResult"]["description"])

        _LOGGER.debug("API request succeeded, payload=%s", self.redact(payload))
        return payload

    def httpx_exception(self, exc: Exception) -> None:
        if isinstance(exc, httpx.TimeoutException):
            msg = f"HTTP request timeout: {exc}"
            _LOGGER.debug("API error: %s", msg)
            raise KingspanTimeoutError(msg) from exc

        msg = f"HTTP request failed: {exc}"
        _LOGGER.debug("API error: %s", msg)
        raise KingspanAPIError(msg) from exc

    def get_history_request(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[str, dict[str, str | dict]]:
        """Build a call history request for all clients."""
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)  # noqa: DTZ006
        if end_date is None:
            end_date_dt = datetime.now()  # noqa: DTZ005

        return (
            "/v1/V1_SoapMobileApp/GetCallHistory_v1_Async",
            {
                "userIdPairWithSN": {
                    "userId": self._user_id,
                    "signalmanNo": signalman_no,
                    "password": self._password,
                },
                "startDate": start_date_dt.isoformat(),
                "endDate": end_date_dt.isoformat(),
            },
        )


class SensorClient(_BaseClient):
    """Synchronous client for interacting with the Kingspan Connect Sensor API."""

    def __init__(self) -> None:
        """Init for Synchronous client."""
        super().__init__()
        self._client = httpx.Client()

    def _request(self, endpoint: str, data: dict[str, str | dict]) -> dict:
        try:
            (url, headers, content) = self.build_request(endpoint, data)
            response = self._client.post(url, headers=headers, content=content)
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            self.httpx_exception(e)

        return self.check_payload(response)

    def login(self, username: str, password: str) -> None:
        """Authenticate with the SOAP API and initialize tank list."""
        self._username = username
        self._password = password
        response = self._request(
            "/v3/V3_SoapMobileApp/Authenticate_v3_Async",
            {"emailAddress": self._username, "password": self._password},
        )

        self._user_id = response["apiUserID"]
        for tank_info in response["tanks"]:
            self._tanks.append(Tank(self, tank_info["signalmanNo"]))

    @property
    def tanks(self) -> list[Tank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    def _get_latest_level(self, signalman_no: str) -> dict:
        """Get the latest level reading for a given tank."""
        return self._request(
            "/v1/V1_SoapMobileApp/GetLatestLevel_v1_Async?culture=EN",
            {
                "userId": self._user_id,
                "signalmanNo": signalman_no,
                "password": self._password,
            },
        )

    def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        (endpoint, data) = self.get_history_request(signalman_no, start_date, end_date)
        response = self._request(endpoint, data)
        return response["levels"]


class AsyncSensorClient(_BaseClient):
    """Asynchronous client for interacting with the Kingspan Connect Sensor API."""

    async def __aenter__(self):  # noqa: ANN204
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):  # noqa: ANN204, ANN001
        """Exit the async context manager."""

    async def _init_client(self) -> httpx.AsyncClient:
        # httpx.AsyncClient loads certificates in a blocking manner which is flagged
        # by Home Assistant, so we run in its own thread once on the first request.
        def _build_client() -> httpx.AsyncClient:
            return httpx.AsyncClient()

        loop = get_running_loop()
        return await loop.run_in_executor(None, _build_client)

    async def _request(self, endpoint: str, data: dict[str, str | list | dict]) -> dict:
        if self._client is None:
            self._client = await self._init_client()

        try:
            (url, headers, content) = self.build_request(endpoint, data)
            response = await self._client.post(url, headers=headers, content=content)
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPError) as e:
            self.httpx_exception(e)

        return self.check_payload(response)

    async def login(self, username: str, password: str) -> None:
        """Authenticate with the SOAP API and initialize tank list."""
        self._username = username
        self._password = password
        response = await self._request(
            "/v3/V3_SoapMobileApp/Authenticate_v3_Async",
            {"emailAddress": self._username, "password": self._password},
        )

        self._user_id = response["apiUserID"]
        for tank_info in response["tanks"]:
            self._tanks.append(AsyncTank(self, tank_info["signalmanNo"]))

    @async_property
    async def tanks(self) -> list[AsyncTank]:
        """Return the list of AsyncTank objects for the authenticated user."""
        return self._tanks

    async def _get_latest_level(self, signalman_no: str) -> dict:
        """Get the latest level reading for a given tank."""
        return await self._request(
            "/v1/V1_SoapMobileApp/GetLatestLevel_v1_Async?culture=EN",
            {
                "userId": self._user_id,
                "signalmanNo": signalman_no,
                "password": self._password,
            },
        )

    async def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get the call history for a given tank within the specified date range."""
        (endpoint, data) = self.get_history_request(signalman_no, start_date, end_date)
        response = await self._request(endpoint, data)
        return response["levels"]
