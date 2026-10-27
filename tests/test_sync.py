import logging
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from conftest import get_mock_filename, get_mock_response
from mock_data import PASSWORD, USERNAME

from connectsensor import (
    APIVersion,
    KingspanAPIError,
    KingspanInvalidCredentialsError,
    KingspanTimeoutError,
    SensorClient,
)
from connectsensor.exceptions import KingspanErrorCode, KingspanNoDataError


def test_status(mock_sync_httpx_post, mock_wsdl):  # noqa: ARG001
    def check_client(api_version: APIVersion) -> None:
        with SensorClient(api_version) as client:
            client.login(USERNAME, PASSWORD)
            tanks = client.tanks
            assert tanks[0].level == 1000
            assert tanks[0].serial_number == "20001000"
            assert tanks[0].model == "TestModel"
            assert tanks[0].name == "TestTank"
            assert tanks[0].capacity == 2000
            assert tanks[0].last_read.replace(microsecond=0) == datetime(2021, 1, 31, 0, 59, 30)
            tank_history = tanks[0].history()
            assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history[1]["level_percent"] == 95
            assert tank_history[2]["level_litres"] == 1880

    check_client(APIVersion.CONNECT_V1)
    check_client(APIVersion.KNECT_V1)


@pytest.mark.parametrize(
    ("mock_effect", "expected_exception", "expected_code", "match_string"),
    [
        # API Data Exceptions
        (
            httpx.Response(
                200, content=b'{"apiResult": {"code": 1, "description": "Authentication Failed"}}'
            ),
            KingspanInvalidCredentialsError,
            KingspanErrorCode.AUTH_FAILED,
            "Authentication Failed",
        ),
        (
            httpx.Response(
                200, content=b'{"apiResult": {"code": 1, "description": "no level data"}}'
            ),
            KingspanNoDataError,
            KingspanErrorCode.NO_DATA,
            "no level data",
        ),
        (
            httpx.Response(
                200, content=b'{"apiResult": {"code": 1, "description": "test API error"}}'
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
            httpx.RequestError("Connection reset"),
            KingspanAPIError,
            KingspanErrorCode.CANNOT_CONNECT,
            "Network connection failed: Connection reset",
        ),
        (
            httpx.TimeoutException("Read timeout"),
            KingspanTimeoutError,
            KingspanErrorCode.TIMEOUT,
            "HTTP request timeout: Read timeout",
        ),
    ],
)
def test_login_exceptions(mocker, mock_effect, expected_exception, expected_code, match_string):
    """Parameterized test to verify all HTTP, network, and API traps during login."""
    if isinstance(mock_effect, Exception):
        mocker.patch.object(httpx.Client, "post", side_effect=mock_effect)
    else:
        mocker.patch.object(httpx.Client, "post", return_value=mock_effect)

    with SensorClient() as client:
        with pytest.raises(expected_exception, match=match_string) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == expected_code


def test_tank_exception(mocker):
    def mocked_post(_self, url, *args, **kwargs) -> httpx.Response:
        if "GetLatestLevel" in url:
            msg = "Test Exception for GetLatestLevel"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)

    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks
        with pytest.raises(KingspanAPIError, match="Test Exception for GetLatestLevel"):
            _ = tanks[0].level


def test_history_exception(mocker):
    def mocked_post(_self, url, *_args, **kwargs) -> httpx.Response:
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)

    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks
        with pytest.raises(KingspanAPIError, match="Test Exception for GetCallHistory"):
            _ = tanks[0].history()


def test_debug_redaction(mock_sync_httpx_post, caplog):  # noqa: ARG001
    logger = logging.getLogger("connectsensor")
    logger.propagate = True
    caplog.set_level(logging.DEBUG, logger="connectsensor")
    caplog.clear()

    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        log_text = caplog.text
        assert USERNAME not in log_text
        assert PASSWORD not in log_text
        assert "*redacted*" in log_text


def test_caching(mock_sync_httpx_post, mocker):  # noqa: ARG001
    """Verify that multiple data accesses do not trigger repeated API calls."""
    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks
        mock_get_latest = mocker.spy(client, "_get_latest_level")

        _ = tanks[0].level
        _ = tanks[0].level
        assert mock_get_latest.call_count == 1

        tanks[0].clear_cache()
        _ = tanks[0].level
        assert mock_get_latest.call_count == 2


def test_soap_parse_exception(mocker, mock_sync_httpx_post, mock_wsdl):  # noqa: ARG001
    """Verify that XML/Zeep serialization crashes are caught and translated."""
    mocker.patch("connectsensor.client.serialize_object", side_effect=Exception("Zeep crash"))

    with SensorClient(APIVersion.CONNECT_V1) as client:
        with pytest.raises(
            KingspanAPIError, match="Unexpected error parsing response: Zeep crash"
        ) as exc_info:
            client.login(USERNAME, PASSWORD)

        assert exc_info.value.code == KingspanErrorCode.UNKNOWN
