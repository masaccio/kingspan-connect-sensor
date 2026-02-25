from datetime import datetime

import httpx
import pandas as pd
import pytest

from conftest import get_mock_filename, get_mock_response
from connectsensor import KingspanAPIError, KingspanInvalidCredentials, SensorClient
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


def test_login_exception(mock_sync_httpx_post):
    client = SensorClient()
    with pytest.raises(
        KingspanInvalidCredentials,
        match="Authentication Failed, Invalid Login",
    ):
        client.login("invalid_user", "invalid_password")


def test_tank_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):
        if "GetLatestLevel" in url:
            raise KingspanAPIError("Test Exception for GetLatestLevel")
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, open(mock_filename, "rb").read())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)

    client = SensorClient()
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks

    with pytest.raises(
        KingspanAPIError,
        match="Test Exception for GetLatestLevel",
    ):
        _ = tanks[0].level


def test_history_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):
        if "GetCallHistory" in url:
            raise KingspanAPIError("Test Exception for GetCallHistory")
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, open(mock_filename, "rb").read())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)
    client = SensorClient()
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks

    with pytest.raises(
        KingspanAPIError,
        match="Test Exception for GetCallHistory",
    ):
        _ = tanks[0].history
