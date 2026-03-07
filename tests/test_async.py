import logging
from datetime import datetime

import httpx
import pytest

from conftest import get_mock_filename, get_mock_response
from connectsensor import (
    APIVersion,
    AsyncSensorClient,
    KingspanAPIError,
    KingspanInvalidCredentialsError,
)
from mock_data import PASSWORD, USERNAME


@pytest.mark.asyncio
async def test_status(mock_async_httpx_post, mock_wsdl):  # noqa: ARG001
    async def check_client(api_version: APIVersion) -> None:
        async with AsyncSensorClient(api_version) as client:
            await client.login(USERNAME, PASSWORD)
            tanks = await client.tanks
            assert await tanks[0].level == 1000
            assert await tanks[0].serial_number == "20001000"
            assert await tanks[0].model == "TestModel"
            assert await tanks[0].name == "TestTank"
            assert await tanks[0].capacity == 2000

            tank_history = await tanks[0].history
            assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history[1]["level_percent"] == 95
            assert tank_history[2]["level_litres"] == 1880

    await check_client(APIVersion.CONNECT_V1)
    await check_client(APIVersion.KNECT_V1)


@pytest.mark.asyncio
async def test_login_exception(mock_async_httpx_post):
    async with AsyncSensorClient() as client:
        with pytest.raises(
            KingspanInvalidCredentialsError,
            match="Authentication Failed, Invalid Login",
        ):
            await client.login("invalid_user", "invalid_password")


@pytest.mark.asyncio
async def test_tank_exception(mocker):
    async def mocked_post(self, url, *args, **kwargs) -> httpx.Response:
        if "GetLatestLevel" in url:
            raise KingspanAPIError("Test Exception for GetLatestLevel")
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, open(mock_filename, "rb").read())

    mocker.patch.object(httpx.AsyncClient, "post", new=mocked_post)

    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        with pytest.raises(
            KingspanAPIError,
            match="Test Exception for GetLatestLevel",
        ):
            _ = await tanks[0].level


@pytest.mark.asyncio
async def test_history_exception(mocker):
    async def mocked_post(self, url, *args, **kwargs):
        if "GetCallHistory" in url:
            raise KingspanAPIError("Test Exception for GetCallHistory")
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, open(mock_filename, "rb").read())

    mocker.patch.object(httpx.AsyncClient, "post", new=mocked_post)

    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        with pytest.raises(
            KingspanAPIError,
            match="Test Exception for GetCallHistory",
        ):
            _ = await tanks[0].history


@pytest.mark.asyncio
async def test_debug_redaction(mock_async_httpx_post, caplog):  # noqa: ARG001
    caplog.set_level(logging.DEBUG, logger="connectsensor")
    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        log_text = caplog.text
        assert len(log_text.splitlines()) == 2
        assert USERNAME not in log_text
        assert PASSWORD not in log_text
        assert "*redacted*" in log_text
