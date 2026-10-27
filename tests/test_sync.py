import json
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
            assert tanks[0].last_read.replace(microsecond=0) == datetime(
                2021,
                1,
                31,
                0,
                59,
                30,
            )
            tank_history = tanks[0].history()
            assert tank_history[0]["reading_date"] == datetime(2021, 1, 25, 13, 59, 14)
            assert tank_history[1]["level_percent"] == 95
            assert tank_history[2]["level_litres"] == 1880

    check_client(APIVersion.CONNECT_V1)
    check_client(APIVersion.KNECT_V1)


def test_login_exception(mock_sync_httpx_post):  # noqa: ARG001
    with SensorClient() as client:
        with pytest.raises(
            KingspanInvalidCredentialsError,
            match="Authentication Failed, Invalid Login",
        ) as exc_info:
            client.login("invalid_user", "invalid_password")
        assert exc_info.value.code == KingspanErrorCode.AUTH_FAILED


def test_unknown_api_error(mocker):
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps({"apiResult": {"code": 1, "description": "test API error"}}).encode(
            "utf-8"
        ),
    )
    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    with SensorClient() as client:
        with pytest.raises(
            KingspanAPIError,
            match="test API error",
        ) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.CANNOT_CONNECT


def test_no_data_error(mocker):
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps(
            {"apiResult": {"code": 1, "description": "Tank has no level data at the moment"}}
        ).encode("utf-8"),
    )
    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    with SensorClient() as client:
        with pytest.raises(
            KingspanNoDataError,
            match="no level data",
        ) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.NO_DATA


def test_network_error(mocker):
    mocker.patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.RequestError("Connection reset"),
    )

    with SensorClient() as client:
        with pytest.raises(
            KingspanAPIError,
            match="Network connection failed: Connection reset",
        ) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.CANNOT_CONNECT


def test_timeout(mocker):
    mocker.patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.TimeoutException("Test httpx timeout"),
    )

    with SensorClient() as client:
        with pytest.raises(
            KingspanTimeoutError,
            match="HTTP request timeout: Test httpx timeout",
        ) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.TIMEOUT


def test_api_unauthorized(mocker):
    mock_response = httpx.Response(status_code=401, content=b"Unauthorized")

    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    with SensorClient() as client:
        with pytest.raises(KingspanAPIError, match="Invalid token authorization") as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.UNKNOWN


def test_malformed_response(mocker):
    mock_response = httpx.Response(
        status_code=200, content=json.dumps({"unexpected": "data"}).encode("utf-8")
    )

    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    with SensorClient() as client:
        with pytest.raises(
            KingspanAPIError,
            match="Malformed response from API: cannot extract response/code",
        ) as exc_info:
            client.login(USERNAME, PASSWORD)
        assert exc_info.value.code == KingspanErrorCode.UNKNOWN


def test_tank_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):  # noqa: ANN003, ARG001
        if "GetLatestLevel" in url:
            msg = "Test Exception for GetLatestLevel"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)

    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks

        with pytest.raises(
            KingspanAPIError,
            match="Test Exception for GetLatestLevel",
        ):
            _ = tanks[0].level


def test_history_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):  # noqa: ANN003
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg, KingspanErrorCode.UNKNOWN)
        mock_filename = get_mock_filename(url, kwargs["content"])
        return get_mock_response(url, Path(mock_filename).read_bytes())

    mocker.patch.object(httpx.Client, "post", new=mocked_post)
    with SensorClient() as client:
        client.login(USERNAME, PASSWORD)
        tanks = client.tanks

        with pytest.raises(
            KingspanAPIError,
            match="Test Exception for GetCallHistory",
        ):
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

        # Access property twice, should only fetch once
        _ = tanks[0].level
        _ = tanks[0].level

        assert mock_get_latest.call_count == 1

        # Clear cache and assert a new call is made
        tanks[0].clear_cache()
        _ = tanks[0].level

        assert mock_get_latest.call_count == 2
