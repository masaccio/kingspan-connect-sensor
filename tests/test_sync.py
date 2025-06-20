from datetime import datetime

import pandas as pd
import pytest
from zeep.exceptions import Error as ZeepError

from connectsensor import APIError, SensorClient
from mock_data import PASSWORD, USERNAME


def test_status(mock_sync_httpx_post):  # noqa: ARG001
    client = SensorClient()
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks
    assert tanks[0].level == 1000
    assert tanks[0].serial_number == "20001000"
    assert tanks[0].model == "TestModel"
    assert tanks[0].name == "TestTank"
    assert tanks[0].capacity == 2000
    tank_history = pd.DataFrame(tanks[0].history)
    reading_date = tank_history.reading_date[0].to_pydatetime()
    assert reading_date == datetime(2021, 1, 25, 13, 59, 14)
    assert tank_history.level_percent[1] == 95
    assert tank_history.level_litres[2] == 1880


def zeep_exception(*args, **kwargs):
    raise ZeepError("Test error")


def test_login_exception(mock_sync_httpx_post):
    client = SensorClient()
    client._soap_client.service.SoapMobileAPPAuthenicate_v3 = (  # noqa: SLF001
        zeep_exception
    )

    with pytest.raises(
        APIError,
        match="Zeep error during login: Test error",
    ):
        client.login("invalid_user", "invalid_password")


def test_tank_exception(mock_sync_httpx_post):
    client = SensorClient()
    client._soap_client.service.SoapMobileAPPGetLatestLevel_v3 = (  # noqa: SLF001
        zeep_exception
    )
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks

    with pytest.raises(
        APIError,
        match="Zeep error fetching tank data: Test error",
    ):
        tanks[0].level


def test_history_exception(mock_sync_httpx_post):
    client = SensorClient()
    client._soap_client.service.SoapMobileAPPGetCallHistory_v1 = (  # noqa: SLF001
        zeep_exception
    )
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks

    with pytest.raises(
        APIError,
        match="Zeep error fetching tank history: Test error",
    ):
        tanks[0].history
