"""Shared tests for synchronous and asynchronous Kingspan Connect Sensor clients."""

from __future__ import annotations

import inspect
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import pytest

from connectsensor import (
    APIVersion,
    AsyncSensorClient,
    KingspanAPIError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
    SensorClient,
)
from connectsensor.exceptions import KingspanInvalidResponseError
from tests.conftest import get_mock_filename, get_mock_response
from tests.mock_data import PASSWORD, USERNAME

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

    from pytest_mock import MockerFixture


async def _resolve(value: Any) -> Any:
    """Await a value if it is awaitable, otherwise return it directly."""
    if inspect.isawaitable(value):
        return await value
    return value


@asynccontextmanager
async def _open_client(
    *,
    is_async: bool,
    version: APIVersion = APIVersion.KNECT_V1,
) -> AsyncIterator[SensorClient | AsyncSensorClient]:
    """Open either SensorClient or AsyncSensorClient with a uniform async interface."""
    if is_async:
        async with AsyncSensorClient(version) as client:
            yield client
    else:
        with SensorClient(version) as client:
            yield client


def _patch_post(
    mocker: MockerFixture,
    *,
    is_async: bool,
    handler: Callable[[str, dict[str, Any]], httpx.Response] | None = None,
    mock_effect: httpx.Response | Exception | None = None,
) -> None:
    """Patch httpx.Client.post or httpx.AsyncClient.post with a sync/async wrapper."""
    target = httpx.AsyncClient if is_async else httpx.Client

    if handler is not None:
        if is_async:

            async def _async_post(
                _self: httpx.AsyncClient,
                url: str,
                *_args: Any,
                **kwargs: Any,
            ) -> httpx.Response:
                return handler(url, kwargs)

            mocker.patch.object(target, "post", new=_async_post)
        else:

            def _sync_post(
                _self: httpx.Client,
                url: str,
                *_args: Any,
                **kwargs: Any,
            ) -> httpx.Response:
                return handler(url, kwargs)

            mocker.patch.object(target, "post", new=_sync_post)
        return

    if isinstance(mock_effect, Exception):
        mocker.patch.object(target, "post", side_effect=mock_effect)
    else:
        mocker.patch.object(target, "post", return_value=mock_effect)


def _file_mock_response(url: str, kwargs: dict[str, Any]) -> httpx.Response:
    """Load the standard file-based mock response for a given request."""
    mock_filename = get_mock_filename(url, kwargs["content"])
    return get_mock_response(url, Path(mock_filename).read_bytes())


LOGIN_EXCEPTION_CASES: list[
    tuple[httpx.Response | Exception, type[KingspanAPIError], KingspanErrorCode, str]
] = [
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
        KingspanInvalidResponseError,
        KingspanErrorCode.INVALID_RESPONSE,
        "Malformed response from API: cannot parse JSON",
    ),
    (
        httpx.Response(200, content=b'["not", "a", "dict"]'),
        KingspanInvalidResponseError,
        KingspanErrorCode.INVALID_RESPONSE,
        "Malformed response from API: expected dict",
    ),
    (
        httpx.Response(200, content=b'{"unexpected": "data"}'),
        KingspanInvalidResponseError,
        KingspanErrorCode.INVALID_RESPONSE,
        "Malformed response from API: cannot extract response/code",
    ),
    (
        httpx.Response(
            200,
            content=b'{"apiResult": {"code": 0}, "apiUserID": "BOX1", "tanks": "not-a-list"}',
        ),
        KingspanInvalidResponseError,
        KingspanErrorCode.INVALID_RESPONSE,
        "Malformed login response",
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
]

MALFORMED_LEVEL_CASES: list[tuple[bytes, str]] = [
    (
        b'{"apiResult": {"code": 0}, "level": "not-a-dict", "tankInfo": []}',
        "Malformed latest level response",
    ),
    (
        (
            b'{"apiResult": {"code": 0}, '
            b'"level": {"levelLitres": 1000, "readingDate": "not-a-date"}, "tankInfo": []}'
        ),
        "Invalid ISO datetime for 'readingDate'",
    ),
    (
        (
            b'{"apiResult": {"code": 0}, '
            b'"level": {"levelLitres": 1000, "readingDate": 12345}, "tankInfo": []}'
        ),
        "Expected datetime or str for 'readingDate'",
    ),
]

MALFORMED_HISTORY_CASES: list[tuple[bytes, str]] = [
    (
        b'{"apiResult": {"code": 0}, "levels": "not-a-list"}',
        "Malformed history response",
    ),
    (
        b'{"apiResult": {"code": 0}, "levels": ["not-a-dict"]}',
        "Malformed history response",
    ),
]


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_httpx_post", "mock_wsdl")
@pytest.mark.parametrize("api_version", [APIVersion.CONNECT_V1, APIVersion.KNECT_V1])
async def test_status(is_async: bool, api_version: APIVersion) -> None:
    """Verify status and history retrieval across API versions."""
    async with _open_client(is_async=is_async, version=api_version) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        assert tanks[0].serial_number == "20001000"
        assert await _resolve(tanks[0].level) == 1000
        assert await _resolve(tanks[0].model) == "TestModel"
        assert await _resolve(tanks[0].name) == "TestTank"
        assert await _resolve(tanks[0].capacity) == 2000
        last_read = await _resolve(tanks[0].last_read)
        assert last_read.replace(microsecond=0) == datetime(2021, 1, 31, 0, 59, 30)
        tank_history = await _resolve(tanks[0].history())
        assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
        assert tank_history[1].get("level_percent") == 95
        assert tank_history[2]["level_litres"] == 1880


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mock_effect", "expected_exception", "expected_code", "match_string"),
    LOGIN_EXCEPTION_CASES,
)
async def test_login_exceptions(  # noqa: PLR0913, PLR0917
    mocker: MockerFixture,
    is_async: bool,
    mock_effect: httpx.Response | Exception,
    expected_exception: type[KingspanAPIError],
    expected_code: KingspanErrorCode,
    match_string: str,
) -> None:
    """Verify HTTP, network, parsing, and API traps during login."""
    _patch_post(mocker, is_async=is_async, mock_effect=mock_effect)

    async with _open_client(is_async=is_async) as client:
        with pytest.raises(expected_exception, match=match_string) as exc_info:
            await _resolve(client.login(USERNAME, PASSWORD))
        assert exc_info.value.code == expected_code


@pytest.mark.asyncio
async def test_tank_exception(mocker: MockerFixture, is_async: bool) -> None:
    """Verify API errors raised while fetching latest tank level are propagated."""

    def handler(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if "GetLatestLevel" in url:
            msg = "Test Exception for GetLatestLevel"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        return _file_mock_response(url, kwargs)

    _patch_post(mocker, is_async=is_async, handler=handler)

    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        with pytest.raises(KingspanAPIError, match="Test Exception for GetLatestLevel"):
            await _resolve(tanks[0].level)


@pytest.mark.asyncio
async def test_history_exception(mocker: MockerFixture, is_async: bool) -> None:
    """Verify API errors raised while fetching tank history are propagated."""

    def handler(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        return _file_mock_response(url, kwargs)

    _patch_post(mocker, is_async=is_async, handler=handler)

    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        with pytest.raises(KingspanAPIError, match="Test Exception for GetCallHistory"):
            await _resolve(tanks[0].history())


@pytest.mark.asyncio
@pytest.mark.parametrize(("payload", "match_string"), MALFORMED_LEVEL_CASES)
async def test_malformed_latest_level_responses(
    mocker: MockerFixture,
    is_async: bool,
    payload: bytes,
    match_string: str,
) -> None:
    """Verify malformed GetLatestLevel payloads raise KingspanInvalidResponseError."""

    def handler(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if "GetLatestLevel" in url:
            return httpx.Response(200, content=payload)
        return _file_mock_response(url, kwargs)

    _patch_post(mocker, is_async=is_async, handler=handler)

    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        with pytest.raises(KingspanInvalidResponseError, match=match_string) as exc_info:
            await _resolve(tanks[0].level)
        assert exc_info.value.code == KingspanErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
@pytest.mark.parametrize(("payload", "match_string"), MALFORMED_HISTORY_CASES)
async def test_malformed_history_responses(
    mocker: MockerFixture,
    is_async: bool,
    payload: bytes,
    match_string: str,
) -> None:
    """Verify malformed GetCallHistory payloads raise KingspanInvalidResponseError."""

    def handler(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if "GetCallHistory" in url:
            return httpx.Response(200, content=payload)
        return _file_mock_response(url, kwargs)

    _patch_post(mocker, is_async=is_async, handler=handler)

    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        with pytest.raises(KingspanInvalidResponseError, match=match_string) as exc_info:
            await _resolve(tanks[0].history())
        assert exc_info.value.code == KingspanErrorCode.INVALID_RESPONSE


@pytest.mark.asyncio
async def test_history_edge_cases(mocker: MockerFixture, is_async: bool) -> None:
    """Verify null levels list and entries without levelPercentage are handled."""
    responses = iter(
        [
            httpx.Response(200, content=b'{"apiResult": {"code": 0}, "levels": null}'),
            httpx.Response(
                200,
                content=(
                    b'{"apiResult": {"code": 0}, "levels": ['
                    b'{"readingDate": "2021-01-25T13:59:14.00", "levelLitres": 2000}'
                    b"]}"
                ),
            ),
        ],
    )

    def handler(url: str, kwargs: dict[str, Any]) -> httpx.Response:
        if "GetCallHistory" in url:
            return next(responses)
        return _file_mock_response(url, kwargs)

    _patch_post(mocker, is_async=is_async, handler=handler)

    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        assert await _resolve(tanks[0].history()) == []

        history = await _resolve(tanks[0].history())
        assert len(history) == 1
        assert history[0]["level_litres"] == 2000.0
        assert "level_percent" not in history[0]


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_httpx_post", "mock_wsdl")
@pytest.mark.parametrize("api_version", [APIVersion.KNECT_V1, APIVersion.CONNECT_V1])
async def test_debug_redaction(
    caplog: pytest.LogCaptureFixture,
    is_async: bool,
    api_version: APIVersion,
) -> None:
    """Verify sensitive credentials are redacted from debug logs."""
    logger = logging.getLogger("connectsensor")
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="connectsensor")
    caplog.clear()

    async with _open_client(is_async=is_async, version=api_version) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        log_text = caplog.text
        assert USERNAME not in log_text
        assert PASSWORD not in log_text
        assert "*redacted*" in log_text


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_httpx_post")
async def test_caching(mocker: MockerFixture, is_async: bool) -> None:
    """Verify that multiple data accesses do not trigger repeated API calls."""
    async with _open_client(is_async=is_async) as client:
        await _resolve(client.login(USERNAME, PASSWORD))
        tanks = await _resolve(client.tanks)
        mock_get_latest = mocker.spy(client, "_get_latest_level")

        await _resolve(tanks[0].level)
        await _resolve(tanks[0].level)
        assert mock_get_latest.call_count == 1

        tanks[0].clear_cache()
        await _resolve(tanks[0].level)
        assert mock_get_latest.call_count == 2


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_httpx_post", "mock_wsdl")
async def test_soap_parse_exception(mocker: MockerFixture, is_async: bool) -> None:
    """Verify that XML/Zeep serialization crashes are caught and translated."""
    mocker.patch("connectsensor.client.serialize_object", side_effect=Exception("Zeep crash"))

    async with _open_client(is_async=is_async, version=APIVersion.CONNECT_V1) as client:
        with pytest.raises(
            KingspanInvalidResponseError,
            match="Unexpected error parsing response: Zeep crash",
        ) as exc_info:
            await _resolve(client.login(USERNAME, PASSWORD))

        assert exc_info.value.code == KingspanErrorCode.INVALID_RESPONSE
