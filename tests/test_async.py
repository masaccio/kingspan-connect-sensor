import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from conftest import get_mock_filename, get_mock_response
from connectsensor import (
    APIVersion,
    AsyncSensorClient,
    KingspanAPIError,
    KingspanInvalidCredentialsError,
)
from connectsensor.client import AsyncSensorClient
from connectsensor.const import APIVersion
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
            last_read = await tanks[0].last_read
            assert last_read.replace(microsecond=0) == datetime(2021, 1, 31, 0, 59, 30)
            tank_history = await tanks[0].history()
            assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history[1]["level_percent"] == 95
            assert tank_history[2]["level_litres"] == 1880

    await check_client(APIVersion.CONNECT_V1)
    await check_client(APIVersion.KNECT_V1)


@pytest.mark.asyncio
async def test_login_exception(mock_async_httpx_post):  # noqa: ARG001
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
            msg = "Test Exception for GetLatestLevel"
            raise KingspanAPIError(msg)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

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
async def test_init_exception(mocker):
    mocker.patch(
        "httpx.AsyncClient",
        side_effect=httpx.HTTPError("Test zeep init"),
    )
    with pytest.raises(KingspanAPIError, match="Test zeep init"):
        async with AsyncSensorClient(version=APIVersion.CONNECT_V1) as _:
            pass


@pytest.mark.asyncio
async def test_history_exception(mocker):
    async def mocked_post(self, url, *args, **kwargs):
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

    mocker.patch.object(httpx.AsyncClient, "post", new=mocked_post)

    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        with pytest.raises(
            KingspanAPIError,
            match="Test Exception for GetCallHistory",
        ):
            _ = await tanks[0].history()


@pytest.mark.asyncio
async def test_debug_redaction(
    mock_async_httpx_post,  # noqa: ARG001
    mock_wsdl,  # noqa: ARG001
    caplog,
):
    async def check_client(api_version: APIVersion) -> None:
        logger = logging.getLogger("connectsensor")
        logger.propagate = True
        caplog.set_level(logging.DEBUG, logger="connectsensor")
        caplog.clear()
        async with AsyncSensorClient(api_version) as client:
            await client.login(USERNAME, PASSWORD)
            log_text = caplog.text
            assert USERNAME not in log_text
            assert PASSWORD not in log_text
            assert "*redacted*" in log_text

    await check_client(APIVersion.CONNECT_V1)
    await check_client(APIVersion.KNECT_V1)


@pytest.mark.asyncio
async def test_async_client_injection():
    """Verify injected HTTPX clients bypass internal lifecycle management."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    # Test 1: Injected client should NOT be closed on __aexit__
    async with AsyncSensorClient(
        version=APIVersion.KNECT_V1,
        client=mock_client,
    ) as client:
        assert client._injected_client is True
        assert client._client == mock_client

    mock_client.aclose.assert_not_called()

    # Test 2: Internally created client MUST be closed on __aexit__
    with patch(
        "connectsensor.client.httpx.AsyncClient",
        autospec=True,
    ) as mock_internal_class:
        mock_internal_instance = mock_internal_class.return_value

        async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
            assert client._injected_client is False
            assert client._client == mock_internal_instance

        mock_internal_instance.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_caching(mock_async_httpx_post, mocker):
    """Verify that multiple async data accesses do not trigger repeated API calls."""
    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks

        mock_get_latest = mocker.spy(client, "_get_latest_level")

        # Access property twice, should only fetch once
        _ = await tanks[0].level
        _ = await tanks[0].level

        assert mock_get_latest.call_count == 1

        # Clear cache and assert a new call is made
        tanks[0].clear_cache()
        _ = await tanks[0].level

        assert mock_get_latest.call_count == 2
