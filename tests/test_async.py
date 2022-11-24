import pytest

from datetime import datetime
from unittest.mock import patch
from zeep.transports import AsyncTransport

from mock_data import VALID_STATUS, USERNAME, PASSWORD
from mock_requests import MockResponse, mock_load_remote_data, async_mock_post

from connectsensor import __version__, AsyncConnectSensor


@pytest.mark.asyncio
async def test_status():
    with patch.object(
        AsyncTransport,
        "_load_remote_data",
        side_effect=mock_load_remote_data,
    ) as mock_get, patch.object(
        AsyncTransport,
        "post_xml",
        side_effect=async_mock_post,
    ) as mock_post:
        async with AsyncConnectSensor() as client:
            await client.login(USERNAME, PASSWORD)
            tanks = await client.tanks
            tank_level = await tanks[0].level
            assert await tanks[0].level == 1000
            assert await tanks[0].serial_number == "20001000"
            assert await tanks[0].model == "TestModel"
            assert await tanks[0].name == "TestTank"
            assert await tanks[0].capacity == 2000
            tank_history = await tanks[0].history
            assert tank_history.reading_date[0] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history.level_percent[1] == 95
            assert tank_history.level_litres[2] == 1880
