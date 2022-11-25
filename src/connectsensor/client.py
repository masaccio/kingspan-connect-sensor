from async_property import async_property
from datetime import datetime
from urllib.parse import urljoin
from zeep import Client as SoapClient
from zeep import AsyncClient as AsyncSoapClient

from .tank import Tank, AsyncTank
from .exceptions import APIError

DEAFULT_SERVER = "https://www.connectsensor.com/"
WSDL_PATH = "soap/MobileApp.asmx?WSDL"
WSDL_URL = urljoin(DEAFULT_SERVER, WSDL_PATH)


class SensorClient:
    def __init__(self):
        self._soap_client = SoapClient(WSDL_URL)
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
    def __init__(self, base=DEAFULT_SERVER):
        url = urljoin(base, WSDL_PATH)
        self._soap_client = AsyncSoapClient(url)
        self._soap_client.set_ns_prefix(None, "http://mobileapp/")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        pass

    async def login(self, username, password):
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
