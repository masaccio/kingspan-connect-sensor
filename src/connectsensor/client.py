"""Client for interacting with the Kingspan Connect Sensor."""

import logging
from asyncio import get_running_loop
from datetime import datetime
from urllib.parse import urljoin

import httpx
from async_property import async_property
from zeep import AsyncClient as AsyncSoapClient
from zeep import Client as SoapClient
from zeep.exceptions import Error as ZeepError
from zeep.transports import AsyncTransport, Transport

from connectsensor.exceptions import APIError
from connectsensor.tank import AsyncTank, Tank

DEFAULT_SERVER = "https://www.connectsensor.com/"
WSDL_PATH = "soap/MobileApp.asmx?WSDL"
WSDL_URL = urljoin(DEFAULT_SERVER, WSDL_PATH)

_LOGGER: logging.Logger = logging.getLogger(__package__)
_LOGGER.debug("Using WSDL URL: %s", WSDL_URL)


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


class SensorClient:
    """Synchronous client for interacting with the Kingspan Connect Sensor SOAP API."""

    def __init__(self) -> None:
        """Initialize the SensorClient with a SOAP client."""
        self._soap_client = SoapClient(WSDL_URL, transport=HttpxTransport())
        self._soap_client.set_ns_prefix(None, "http://mobileapp/")

    def login(self, username: str, password: str) -> None:
        """Authenticate with the SOAP API and initialize tank list."""
        self._username = username
        self._password = password

        try:
            response = self._soap_client.service.SoapMobileAPPAuthenicate_v3(
                emailaddress=username,
                password=password,
            )
        except ZeepError as e:
            _LOGGER.debug("Zeep error during login: %s", e)
            msg = f"Zeep error during login: {e}"
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])

            self._user_id = response["APIUserID"]
            self._tanks = []
            for tank_info in response["Tanks"]["APITankInfo_V3"]:
                self._tanks.append(Tank(self, tank_info["SignalmanNo"]))
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e

    @property
    def tanks(self) -> list[Tank]:
        """Return the list of Tank objects for the authenticated user."""
        return self._tanks

    def _get_latest_level(self, signalman_no: str) -> dict:
        """Get the latest level reading for a given tank."""
        try:
            response = self._soap_client.service.SoapMobileAPPGetLatestLevel_v3(
                userid=self._user_id,
                password=self._password,
                signalmanno=signalman_no,
                culture="en",
            )
        except ZeepError as e:
            _LOGGER.debug("Zeep error fetching tank data: %s", e)
            msg = f"Zeep error fetching tank data: {e}"
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e
        else:
            return response

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

        try:
            response = self._soap_client.service.SoapMobileAPPGetCallHistory_v1(
                userid=self._user_id,
                password=self._password,
                signalmanno=signalman_no,
                startdate=start_date_dt.isoformat(),
                enddate=end_date_dt.isoformat(),
            )
        except ZeepError as e:
            _LOGGER.debug("Zeep error fetching tank history: %s", e)
            msg = f"Zeep error fetching tank history: {e}"
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e
        else:
            return response["Levels"]["APILevel"]


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
        wsdl_client = httpx.Client()
        httpx_client = httpx.AsyncClient()
        transport = AsyncTransport(client=httpx_client, wsdl_client=wsdl_client)

        try:
            self._soap_client = await loop.run_in_executor(
                None,
                lambda: AsyncSoapClient(WSDL_URL, transport=transport),
            )
            self._soap_client.set_ns_prefix(None, "http://mobileapp/")
        except ZeepError as e:
            _LOGGER.debug("Zeep error during initialisation: %s", e)
            msg = f"Zeep error during initialisation: {e}"
            raise APIError(msg) from e

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
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])

            self._user_id = response["APIUserID"]
            self._tanks = []
            for tank_info in response["Tanks"]["APITankInfo_V3"]:
                self._tanks.append(AsyncTank(self, tank_info["SignalmanNo"]))
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e
        else:
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
            raise APIError(msg)
        try:
            response = await self._soap_client.service.SoapMobileAPPGetLatestLevel_v3(
                userid=self._user_id,
                password=self._password,
                signalmanno=signalman_no,
                culture="en",
            )
        except ZeepError as e:
            msg = f"Zeep error fetching tank data: {e}"
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e
        else:
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
            raise APIError(msg)
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
            raise APIError(msg) from e

        try:
            if response["APIResult"]["Code"] != 0:
                raise APIError(response["APIResult"]["Description"])
            return response["Levels"]["APILevel"]
        except KeyError as e:
            msg = "Invalid SOAP response"
            _LOGGER.exception(msg)
            raise APIError(msg) from e
