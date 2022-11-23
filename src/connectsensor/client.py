from datetime import datetime
from logging import debug
from urllib.parse import urljoin
from zeep import Client as SoapClient
from zeep import AsyncClient as AsyncSoapClient

from .tank import Tank

DEAFULT_SERVER = "https://www.connectsensor.com/"
WSDL_PATH = "soap/MobileApp.asmx?WSDL"
WSDL_URL = urljoin(DEAFULT_SERVER, WSDL_PATH)


class APIError(Exception):
    pass


class SensorClient:
    def __init__(self):
        self._client = SoapClient(WSDL_URL)
        self._client.set_ns_prefix(None, "http://mobileapp/")

    def login(self, username, password):
        self._username = username
        self._password = password

        debug("login: username={username}")
        response = self._client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )

        if response["APIResult"]["Code"] != 0:
            err_str = response["APIResult"]["Description"]
            debug("login: failed with {err_str}")
            raise APIError()

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(Tank(self, tank_info))

    def tanks(self):
        return self._tanks

    def get_latest_level(self, signalman_no):
        response = self._get_level_transport(signalman_no)

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response

    def get_history(self, signalman_no, start_date=None, end_date=None):
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)
        if end_date is None:
            end_date_dt = datetime.now()

        response = self._get_history_transport(signalman_no, start_date_dt, end_date_dt)

        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])  # pragma: no cover
        return response["Levels"]["APILevel"]

    def _login_transport(self, username, password):
        print(f"sync:_login_transport: username={username}")
        return self._client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )

    def _get_level_transport(self, signalman_no):
        return self._client.service.SoapMobileAPPGetLatestLevel_v3(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            culture="en",
        )

    def _get_history_transport(self, signalman_no, start_date_dt, end_date_dt):
        return self._client.service.SoapMobileAPPGetCallHistory_v1(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            startdate=start_date_dt.isoformat(),
            enddate=end_date_dt.isoformat(),
        )


class AsyncConnectSensor(SensorClient):
    def __init__(self, base=DEAFULT_SERVER):
        debug("AsyncConnectSensor:init")
        url = urljoin(base, WSDL_PATH)
        self._client = AsyncSoapClient(url)
        self._client.set_ns_prefix(None, "http://mobileapp/")

    async def __aenter__(self):
        debug("AsyncConnectSensor:aenter")
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        debug("AsyncConnectSensor:aexit")
        pass

    async def login(self, username, password):
        self._username = username
        self._password = password

        debug("login: username={username}")

        response = await self._client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )

        if response["APIResult"]["Code"] != 0:
            err_str = response["APIResult"]["Description"]
            debug("login: failed with {err_str}")
            raise APIError()

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(Tank(self, tank_info))
        return response

    async def _get_level_transport(self, signalman_no):
        response = await self._client.service.SoapMobileAPPGetLatestLevel_v3(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            culture="en",
        )
        return response

    async def _get_history_transport(self, signalman_no, start_date_dt, end_date_dt):
        response = await self._client.service.SoapMobileAPPGetCallHistory_v1(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            startdate=start_date_dt.isoformat(),
            enddate=end_date_dt.isoformat(),
        )
        return response
