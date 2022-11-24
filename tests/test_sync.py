import pytest

from datetime import datetime
from unittest.mock import patch
from zeep.transports import Transport

from mock_data import VALID_STATUS, USERNAME, PASSWORD
from mock_requests import MockResponse, mock_load_remote_data, mock_post

from connectsensor import __version__, SensorClient


def test_status():
    with patch.object(
        Transport,
        "_load_remote_data",
        side_effect=mock_load_remote_data,
    ) as mock_get, patch.object(
        Transport,
        "post_xml",
        side_effect=mock_post,
    ) as mock_post_func:
        client = SensorClient()
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks
        tank_level = tanks[0].level
        assert tanks[0].level == 1000
        assert tanks[0].serial_number == "20001000"
        assert tanks[0].model == "TestModel"
        assert tanks[0].name == "TestTank"
        assert tanks[0].capacity == 2000
        tank_history = tanks[0].history
        assert tank_history.reading_date[0] == datetime(2021, 1, 25, 13, 59, 14)
        assert tank_history.level_percent[1] == 95
        assert tank_history.level_litres[2] == 1880
