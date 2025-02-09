from async_property import async_property
from datetime import datetime
from urllib.parse import urljoin
from zeep import Client as SoapClient
from zeep import AsyncClient as AsyncSoapClient
from zeep.transports import Transport, AsyncTransport

import httpx

from asyncio import get_running_loop
from .tank import Tank, AsyncTank
from .exceptions import APIError

DEFAULT_SERVER = "https://www.connectsensor.com/"
WSDL_PATH = "soap/MobileApp.asmx?WSDL"
WSDL_URL = urljoin(DEFAULT_SERVER, WSDL_PATH)


class HttpxTransport(Transport):
    def __init__(self):
        super().__init__()
        self.client = httpx.Client()  # Synchronous HTTPX client

    def post(self, address, envelope, headers):  # type: ignore
        """Override the default `post` method to use `httpx.Client`."""
        response = self.client.post(address, data=envelope, headers=headers)
        return response


class SensorClient:
    def __init__(self):
        self._soap_client = SoapClient(WSDL_URL, transport=HttpxTransport())
        self._soap_client.set_ns_prefix(None, "http://mobileapp/")

    def login(self, username, password):
        self._username = username
        self._password = password

        response = self._soap_client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(Tank(self, tank_info["SignalmanNo"]))

    @property
    def tanks(self):
        return self._tanks

    def _get_latest_level(self, signalman_no):
        response = self._soap_client.service.SoapMobileAPPGetLatestLevel_v3(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            culture="en",
        )

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response

    def _get_history(self, signalman_no, start_date=None, end_date=None):
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)
        if end_date is None:
            end_date_dt = datetime.now()

        response = self._soap_client.service.SoapMobileAPPGetCallHistory_v1(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            startdate=start_date_dt.isoformat(),
            enddate=end_date_dt.isoformat(),
        )

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response["Levels"]["APILevel"]


class AsyncSensorClient:
    def __init__(self):
        self._soap_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        pass

    async def _init_zeep(self):
        # Zeep.AsyncClient uses httpx which loads SSL cerficates at
        # construction, so we need to delay creating the connection.
        loop = get_running_loop()
        wsdl_client = httpx.Client()
        httpx_client = httpx.AsyncClient()
        transport = AsyncTransport(client=httpx_client, wsdl_client=wsdl_client)

        self._soap_client = await loop.run_in_executor(
            None, lambda: AsyncSoapClient(WSDL_URL, transport=transport)
        )
        self._soap_client.set_ns_prefix(None, "http://mobileapp/")

    async def login(self, username, password):
        if self._soap_client is None:
            await self._init_zeep()

        self._username = username
        self._password = password

        response = await self._soap_client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(AsyncTank(self, tank_info["SignalmanNo"]))
        return response

    @async_property
    async def tanks(self):
        return self._tanks

    async def _get_latest_level(self, signalman_no):
        response = await self._soap_client.service.SoapMobileAPPGetLatestLevel_v3(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            culture="en",
        )
        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response

    async def _get_history(self, signalman_no, start_date=None, end_date=None):
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)
        if end_date is None:
            end_date_dt = datetime.now()

        response = await self._soap_client.service.SoapMobileAPPGetCallHistory_v1(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            startdate=start_date_dt.isoformat(),
            enddate=end_date_dt.isoformat(),
        )

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response["Levels"]["APILevel"]
