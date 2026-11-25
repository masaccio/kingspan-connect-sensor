"""Tests for the asynchronous Kingspan Connect Sensor client."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import aiofiles
import httpx
import pytest
from zeep import AsyncClient as AsyncSoapClient

from connectsensor import (
    APIVersion,
    AsyncSensorClient,
    KingspanAPIError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)
from tests.conftest import get_mock_filename, get_mock_response
from tests.mock_data import PASSWORD, USERNAME

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_async_httpx_post", "mock_wsdl")
async def test_status() -> None:
    """Verify async client status and history retrieval across API versions."""

    async def check_client(api_version: APIVersion) -> None:
        async with AsyncSensorClient(api_version) as client:
            await client.login(USERNAME, PASSWORD)
            tanks = await client.tanks
            assert tanks[0].serial_number == "20001000"
            assert await tanks[0].level == 1000
            assert await tanks[0].model == "TestModel"
            assert await tanks[0].name == "TestTank"
            assert await tanks[0].capacity == 2000
            last_read = await tanks[0].last_read
            assert last_read.replace(microsecond=0) == datetime(2021, 1, 31, 0, 59, 30)
            tank_history = await tanks[0].history()
            assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history[1].get("level_percent") == 95
            assert tank_history[2]["level_litres"] == 1880

    await check_client(APIVersion.CONNECT_V1)
    await check_client(APIVersion.KNECT_V1)


@pytest.mark.parametrize(
    ("mock_effect", "expected_exception", "expected_code", "match_string"),
    [
        # API Data Exceptions
        (
            httpx.Response(
                200,
                content=b'{"apiResult": {"code": 1, "description": "Authentication Failed"}}',
            ),
            KingspanInvalidCredentialsError,
            KingspanErrorCode.AUTH_FAILED,
            "Authentication Failed",
        ),
        (
            httpx.Response(
                200,
                content=b'{"apiResult": {"code": 1, "description": "no level data"}}',
            ),
            KingspanNoDataError,
            KingspanErrorCode.NO_DATA,
            "no level data",
        ),
        (
            httpx.Response(
                200,
                content=b'{"apiResult": {"code": 1, "description": "test API error"}}',
            ),
            KingspanAPIError,
            KingspanErrorCode.CANNOT_CONNECT,
            "test API error",
        ),
        # Protocol & Parsing Exceptions
        (
            httpx.Response(401, content=b"Unauthorized"),
            KingspanInvalidCredentialsError,
            KingspanErrorCode.AUTH_FAILED,
            "Invalid token authorization",
        ),
        (
            httpx.Response(502, content=b"<html>502 Bad Gateway</html>"),
            KingspanAPIError,
            KingspanErrorCode.UNKNOWN,
            "cannot parse JSON",
        ),
        (
            httpx.Response(200, content=b'{"unexpected": "data"}'),
            KingspanAPIError,
            KingspanErrorCode.UNKNOWN,
            "cannot extract response/code",
        ),
        # Network Trap Exceptions
        (
            httpx.RequestError("Connection refused"),
            KingspanAPIError,
            KingspanErrorCode.CANNOT_CONNECT,
            "Network connection failed: Connection refused",
        ),
        (
            httpx.TimeoutException("Read timeout"),
            KingspanTimeoutError,
            KingspanErrorCode.TIMEOUT,
            "HTTP request timeout: Read timeout",
        ),
    ],
)
@pytest.mark.asyncio
async def test_login_exceptions(
    mocker: MockerFixture,
    mock_effect: httpx.Response | Exception,
    expected_exception: type[KingspanAPIError],
    expected_code: KingspanErrorCode,
    match_string: str,
) -> None:
    """Parameterized test to verify all async HTTP, network, and API traps."""
    if isinstance(mock_effect, Exception):
        mocker.patch.object(httpx.AsyncClient, "post", side_effect=mock_effect)
    else:
        mocker.patch.object(httpx.AsyncClient, "post", return_value=mock_effect)

    async with AsyncSensorClient() as client:
        with pytest.raises(expected_exception, match=match_string) as exc_info:
            await client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_tank_exception(mocker: MockerFixture) -> None:
    """Verify API errors raised while fetching latest tank level are propagated."""

    async def mocked_post(
        _self: httpx.AsyncClient,
        url: str,
        *_args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        if "GetLatestLevel" in url:
            msg = "Test Exception for GetLatestLevel"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        async with aiofiles.open(mock_filename, "rb") as f:
            mock_bytes = await f.read()
        return get_mock_response(url, mock_bytes)

    mocker.patch.object(httpx.AsyncClient, "post", new=mocked_post)

    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks
        with pytest.raises(KingspanAPIError, match="Test Exception for GetLatestLevel"):
            _ = await tanks[0].level


@pytest.mark.asyncio
async def test_init_exception(mocker: MockerFixture) -> None:
    """Verify client initialization failures are wrapped as KingspanAPIError."""
    mocker.patch("httpx.AsyncClient", side_effect=Exception("Test zeep init"))
    with pytest.raises(
        KingspanAPIError,
        match="Unexpected request failure: Test zeep init",
    ) as exc_info:
        async with AsyncSensorClient(version=APIVersion.CONNECT_V1) as _:
            pass
    assert exc_info.value.code == KingspanErrorCode.UNKNOWN


@pytest.mark.asyncio
async def test_history_exception(mocker: MockerFixture) -> None:
    """Verify API errors raised while fetching tank history are propagated."""

    async def mocked_post(
        _self: httpx.AsyncClient,
        url: str,
        *_args: Any,
        **kwargs: Any,
    ) -> httpx.Response:
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        async with aiofiles.open(mock_filename, "rb") as f:
            mock_bytes = await f.read()
        return get_mock_response(url, mock_bytes)

    mocker.patch.object(httpx.AsyncClient, "post", new=mocked_post)

    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks
        with pytest.raises(KingspanAPIError, match="Test Exception for GetCallHistory"):
            _ = await tanks[0].history()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_async_httpx_post", "mock_wsdl")
@pytest.mark.parametrize(("api_version"), [(APIVersion.KNECT_V1), (APIVersion.CONNECT_V1)])
async def test_debug_redaction(
    caplog: pytest.LogCaptureFixture,
    api_version: APIVersion,
) -> None:
    """Verify sensitive credentials are redacted from debug logs."""
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


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_wsdl")
@pytest.mark.parametrize("api_version", [APIVersion.KNECT_V1, APIVersion.CONNECT_V1])
async def test_async_client_injection(api_version: APIVersion) -> None:
    """Verify injected HTTPX clients bypass lifecycle management but WSDL clients are closed."""
    # pylint: disable=protected-access
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("connectsensor.client.httpx.Client", autospec=True) as mock_sync_client:
        mock_wsdl_instance = mock_sync_client.return_value

        async with AsyncSensorClient(version=api_version, client=mock_client) as client:
            assert client._has_injected_client is True
            if api_version == APIVersion.CONNECT_V1:
                assert isinstance(client._client, AsyncSoapClient)
                assert client._client.transport.client == mock_client
            else:
                assert client._client == mock_client

        mock_client.aclose.assert_not_called()

        if api_version == APIVersion.CONNECT_V1:
            mock_wsdl_instance.close.assert_called_once()
        else:
            mock_sync_client.assert_not_called()

    with patch("connectsensor.client.httpx.AsyncClient", autospec=True) as mock_internal:
        mock_internal_instance = mock_internal.return_value

        async with AsyncSensorClient(version=api_version) as client:
            assert client._has_injected_client is False
            if api_version == APIVersion.CONNECT_V1:
                assert isinstance(client._client, AsyncSoapClient)
            else:
                assert client._client == mock_internal_instance

        mock_internal_instance.aclose.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_async_httpx_post")
async def test_caching(mocker: MockerFixture) -> None:
    """Verify that multiple async data accesses do not trigger repeated API calls."""
    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks
        mock_get_latest = mocker.spy(client, "_get_latest_level")

        _ = await tanks[0].level
        _ = await tanks[0].level
        assert mock_get_latest.call_count == 1

        tanks[0].clear_cache()
        _ = await tanks[0].level
        assert mock_get_latest.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_async_httpx_post", "mock_wsdl")
async def test_soap_parse_exception(mocker: MockerFixture) -> None:
    """Verify that XML/Zeep serialization crashes are caught and translated."""
    mocker.patch("connectsensor.client.serialize_object", side_effect=Exception("Zeep crash"))

    async with AsyncSensorClient(APIVersion.CONNECT_V1) as client:
        with pytest.raises(
            KingspanAPIError,
            match="Unexpected error parsing response: Zeep crash",
        ) as exc_info:
            await client.login(USERNAME, PASSWORD)

        assert exc_info.value.code == KingspanErrorCode.UNKNOWN
