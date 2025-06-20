from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest
from zeep.exceptions import Error as ZeepError

from connectsensor import APIError, AsyncSensorClient
from mock_data import PASSWORD, USERNAME


@pytest.mark.asyncio
async def test_status(mock_async_httpx_post):
    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks
        assert await tanks[0].level == 1000
        assert await tanks[0].serial_number == "20001000"
        assert await tanks[0].model == "TestModel"
        assert await tanks[0].name == "TestTank"
        assert await tanks[0].capacity == 2000

        tank_history = await tanks[0].history
        tank_history = pd.DataFrame(tank_history)
        reading_date = tank_history.reading_date[0].to_pydatetime()
        assert reading_date == datetime(2021, 1, 25, 13, 59, 14)
        assert tank_history.level_percent[1] == 95
        assert tank_history.level_litres[2] == 1880


async def zeep_exception(*args, **kwargs):
    raise ZeepError("Test error")


@pytest.mark.asyncio
async def test_login_exception(mock_async_httpx_post):
    async with AsyncSensorClient() as client:
        await client._init_zeep()  # noqa: SLF001
        client._soap_client.service.SoapMobileAPPAuthenicate_v3 = (  # noqa: SLF001
            zeep_exception
        )

        with pytest.raises(
            APIError,
            match="Zeep error during login: Test error",
        ):
            await client.login("invalid_user", "invalid_password")


@pytest.mark.asyncio
async def test_tank_exception(mock_async_httpx_post):
    async with AsyncSensorClient() as client:
        await client._init_zeep()  # noqa: SLF001
        client._soap_client.service.SoapMobileAPPGetLatestLevel_v3 = (  # noqa: SLF001
            zeep_exception
        )
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        with pytest.raises(
            APIError,
            match="Zeep error fetching tank data: Test error",
        ):
            await tanks[0].level


@pytest.mark.asyncio
async def test_history_exception(mock_async_httpx_post):
    async with AsyncSensorClient() as client:
        await client._init_zeep()  # noqa: SLF001
        client._soap_client.service.SoapMobileAPPGetCallHistory_v1 = (  # noqa: SLF001
            zeep_exception
        )
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        with pytest.raises(
            APIError,
            match="Zeep error fetching tank history: Test error",
        ):
            await tanks[0].history
