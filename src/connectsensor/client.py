"""Client for interacting with the Kingspan Connect Sensor."""

import json
import logging
from asyncio import get_running_loop
from datetime import datetime
from urllib.parse import urljoin

import httpx
from async_property import async_property

from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanTimeoutError,
    KingspanInvalidCredentials,
)
from connectsensor.tank import AsyncTank, Tank

# API is HTTP and sends the username and password in the clear
API_SERVER = "sensorapi.connectsensor.com"
API_PORT = 8087
API_BASE_URL = f"http://{API_SERVER}:{API_PORT}"

# The JWT appears to be hard-coded into the application rather than securely returned
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJUaGVNb2JpbGVBcHAiLCJyb2xlIjoiVGhlTW9iaWxlQXBwIiwiZXhwIjoxNzg2ODk4NTM3LCJpc3MiOiJTZW5zb3JBUEkgQXV0aFNlcnZlciIsImF1ZCI6IlNlbnNvckFQSSBVc2VycyJ9.PW-NP46vP9pP5Da87KIzsN6ZWIA3vOI4XbqxHWVuTOY"  # noqa: E501, S105

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("Using API: %s", API_BASE_URL)


class SensorClient:
    """Synchronous client for interacting with the Kingspan Connect Sensor SOAP API."""

    def __init__(self) -> None:
        """Initialize the HTTPX Client."""
        self._client = httpx.Client()

    def _request(self, endpoint: str, data: dict[str, str | dict]) -> dict:
        try:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {TOKEN}",
            }
            url = f"{API_BASE_URL}{endpoint}"
            response = self._client.post(url, headers=headers, content=json.dumps(data))
            response.raise_for_status()
        except httpx.TimeoutException as e:
            msg = f"HTTP request timeout: {e}"
            raise KingspanTimeoutError(msg) from e
        except httpx.HTTPError as e:
            msg = f"HTTP request failed: {e}"
            raise KingspanAPIError(msg) from e

        payload = json.loads(response.content)
        if "apiResult" not in payload or "code" not in payload["apiResult"]:
            msg = "Malformed response from API: cannot extract response/code"
            raise KingspanAPIError(msg)

        if payload["apiResult"]["code"] != 0:
            err = payload["apiResult"]["description"]
            if "Authentication Failed" in err:
                raise KingspanInvalidCredentials(err)
            raise KingspanAPIError(payload["apiResult"]["description"])

        return payload

    def login(self, username: str, password: str) -> None:
        """Authenticate with the SOAP API and initialize tank list."""
        self._username = username
        self._password = password
        response = self._request(
            "/v3/V3_SoapMobileApp/Authenticate_v3_Async",
            {"emailAddress": self._username, "password": self._password},
        )

        self._user_id = response["apiUserID"]
        self._tanks = []
        for tank_info in response["tanks"]:
            self._tanks.append(Tank(self, tank_info["signalmanNo"]))

    @property
    def tanks(self) -> list[Tank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    def _get_latest_level(self, signalman_no: str) -> dict:
        """Get the latest level reading for a given tank."""
        return self._request(
            "/v1/V1_SoapMobileApp/GetLatestLevel_v1_Async",
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
        """Get the call history for a given tank within the specified date range."""
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)  # noqa: DTZ006
        if end_date is None:
            end_date_dt = datetime.now()  # noqa: DTZ005

        response = self._request(
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
        return response["levels"]


class AsyncSensorClient:
    """Asynchronous client for interacting with the Kingspan Connect Sensor SOAP API."""

    def __init__(self) -> None:
        """Initialize the AsyncSensorClient with an async SOAP client."""
        self._soap_client = None

    async def __aenter__(self):  # noqa: ANN204
        """Enter the async context manager."""
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):  # noqa: ANN204, ANN001
        """Exit the async context manager."""

    async def _init_zeep(self) -> None:
        """Initialize the Zeep async SOAP client."""
        # Zeep.AsyncClient uses httpx which loads SSL cerficates at
        # construction, so we need to delay creating the connection.
        loop = get_running_loop()

        def _build_client() -> AsyncSoapClient:
            # Build HTTP in s thread so that load_verify_locations() doesn't
            # block the caller's thread
            wsdl_client = httpx.Client()
            httpx_client = httpx.AsyncClient()
            transport = AsyncTransport(client=httpx_client, wsdl_client=wsdl_client)
            client = AsyncSoapClient(WSDL_URL, transport=transport)
            client.set_ns_prefix(None, "http://mobileapp/")
            return client

        try:
            self._soap_client = await loop.run_in_executor(None, _build_client)
        except ZeepError as e:
            _LOGGER.debug("Zeep error during initialization: %s", e)
            msg = f"Zeep error during initialization: {e}"
            raise KingspanAPIError(msg) from e

    async def login(self, username: str, password: str) -> dict:
        """Authenticate with the SOAP API and initialize async tank list."""
        if self._soap_client is None:
            await self._init_zeep()

        self._username = username
        self._password = password

        _LOGGER.debug("Logging in with username: %s", username)
        try:
            response = await self._soap_client.service.SoapMobileAPPAuthenicate_v3(  # type: ignore[reportOptionalMemberAccess]
                emailaddress=username,
                password=password,
            )
        except (ZeepError, httpx.HTTPError) as e:
            _LOGGER.debug("Zeep error during login: %s", e)
            msg = f"Zeep error during login: {e}"
            raise KingspanAPIError(msg) from e

        # No need to catch KeyErrors here as the WSDL guarantees the structure
        # of the response, so we can assume the keys exist. If not, a ZeepError
        # will have been raised earlier.
        if response["APIResult"]["Code"] != 0:
            raise KingspanAPIError(response["APIResult"]["Description"])

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(AsyncTank(self, tank_info["SignalmanNo"]))
        return response

    @async_property
    async def tanks(self) -> list[AsyncTank]:
        """Return the list of AsyncTank objects for the authenticated user."""
        return self._tanks

    async def _get_latest_level(self, signalman_no: str) -> dict:
        """Get the latest level reading for a given tank asynchronously."""
        if self._soap_client is None:
            await self._init_zeep()
        if self._soap_client is None:
            msg = "SOAP client could not be initialized."
            raise KingspanAPIError(msg)
        try:
            response = await self._soap_client.service.SoapMobileAPPGetLatestLevel_v3(
                userid=self._user_id,
                password=self._password,
                signalmanno=signalman_no,
                culture="en",
            )
        except ZeepError as e:
            msg = f"Zeep error fetching tank data: {e}"
            raise KingspanAPIError(msg) from e

        # No need to catch KeyErrors here as the WSDL guarantees the structure
        # of the response, so we can assume the keys exist. If not, a ZeepError
        # will have been raised earlier.
        if response["APIResult"]["Code"] != 0:
            raise KingspanAPIError(response["APIResult"]["Description"])
        return response

    async def _get_history(
        self,
        signalman_no: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict]:
        """Get the call history for a given tank within the specified date range asynchronously."""
        if self._soap_client is None:
            await self._init_zeep()
        if self._soap_client is None:
            msg = "SOAP client could not be initialized."
            raise KingspanAPIError(msg)
        start_date_dt = (
            datetime.fromtimestamp(0)  # noqa: DTZ006
            if start_date is None
            else start_date
        )
        end_date_dt = datetime.now() if end_date is None else end_date  # noqa: DTZ005
        try:
            response = await self._soap_client.service.SoapMobileAPPGetCallHistory_v1(
                userid=self._user_id,
                password=self._password,
                signalmanno=signalman_no,
                startdate=start_date_dt.isoformat(),
                enddate=end_date_dt.isoformat(),
            )
        except ZeepError as e:
            msg = f"Zeep error fetching tank history: {e}"
            raise KingspanAPIError(msg) from e

        # No need to catch KeyErrors here as the WSDL guarantees the structure
        # of the response, so we can assume the keys exist. If not, a ZeepError
        # will have been raised earlier.
        if response["APIResult"]["Code"] != 0:
            raise KingspanAPIError(response["APIResult"]["Description"])
        return response["Levels"]["APILevel"]
