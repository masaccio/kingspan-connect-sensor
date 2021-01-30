from zeep import Client as SoapClient
from datetime import datetime

from .tank import Tank

WSDL_URL = "https://www.connectsensor.com/soap/MobileApp.asmx?WSDL"


class APIError(Exception):
    pass


class SensorClient:
    def __init__(self):
        self._client = SoapClient(WSDL_URL)
        self._client.set_ns_prefix(None, "http://mobileapp/")

    def login(self, username, password):
        self._username = username
        self._password = password

        response = self._client.service.SoapMobileAPPAuthenicate_v3(
            emailaddress=username, password=password
        )
        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])

        self._user_id = response["APIUserID"]
        self._tanks = []
        for tank_info in response["Tanks"]["APITankInfo_V3"]:
            self._tanks.append(Tank(self, tank_info))

    def tanks(self):
        return self._tanks

    def get_latest_level(self, signalman_no):
        response = self._client.service.SoapMobileAPPGetLatestLevel_v3(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            culture="en",
        )
        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])
        return response

    def get_history(self, signalman_no, start_date=None, end_date=None):
        if start_date is None:
            start_date_dt = datetime.fromtimestamp(0)
        if end_date is None:
            end_date_dt = datetime.now()

        response = self._client.service.SoapMobileAPPGetCallHistory_v1(
            userid=self._user_id,
            password=self._password,
            signalmanno=signalman_no,
            startdate=start_date_dt.isoformat(),
            enddate=end_date_dt.isoformat(),
        )
        if response["APIResult"]["Code"] != 0:
            raise APIError(response["APIResult"]["Description"])
        return response["Levels"]["APILevel"]
