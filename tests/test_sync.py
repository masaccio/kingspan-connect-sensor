import json
import logging
from datetime import datetime

import httpx
import pytest

from conftest import get_mock_filename, get_mock_response
from connectsensor import (
    APIVersion,
    KingspanAPIError,
    KingspanInvalidCredentialsError,
    KingspanTimeoutError,
    SensorClient,
)
from mock_data import PASSWORD, USERNAME


def test_status(mock_sync_httpx_post, mock_wsdl):  # noqa: ARG001
    def check_client(api_version: APIVersion) -> None:
        client = SensorClient(api_version)
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
    client = SensorClient()
    with pytest.raises(
        KingspanInvalidCredentialsError,
        match="Authentication Failed, Invalid Login",
    ):
        client.login("invalid_user", "invalid_password")


def test_unknown_api_error(mocker):
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps(
            {"apiResult": {"code": 1, "description": "test API error"}}
        ).encode("utf-8"),
    )
    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    client = SensorClient()
    with pytest.raises(
        KingspanAPIError,
        match="test API error",
    ):
        client.login(USERNAME, PASSWORD)


def test_tank_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):  # noqa: ANN003, ARG001
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


def test_timeout(mocker):
    mocker.patch.object(
        httpx.Client,
        "post",
        side_effect=httpx.TimeoutException("Test httpx timeout"),
    )

    client = SensorClient()

    with pytest.raises(
        KingspanTimeoutError,
        match="HTTP request timeout: Test httpx timeout",
    ):
        client.login(USERNAME, PASSWORD)


def test_api_unauthorized(mocker):
    mock_response = httpx.Response(status_code=401, content=b"Unauthorized")

    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    client = SensorClient()
    with pytest.raises(KingspanAPIError, match="Invalid token authorization"):
        client.login(USERNAME, PASSWORD)


def test_malformed_response(mocker):
    mock_response = httpx.Response(
        status_code=200, content=json.dumps({"unexpected": "data"}).encode("utf-8")
    )

    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    client = SensorClient()
    with pytest.raises(
        KingspanAPIError,
        match="Malformed response from API: cannot extract response/code",
    ):
        client.login(USERNAME, PASSWORD)


def test_history_exception(mocker):
    def mocked_post(self, url, *args, **kwargs):
        if "GetCallHistory" in url:
            msg = "Test Exception for GetCallHistory"
            raise KingspanAPIError(msg)
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
        _ = tanks[0].history()


def test_debug_redaction(mock_sync_httpx_post, caplog):  # noqa: ARG001
    caplog.set_level(logging.DEBUG, logger="connectsensor")
    client = SensorClient()
    client.login(USERNAME, PASSWORD)
    log_text = caplog.text
    assert len(log_text.splitlines()) == 2
    assert USERNAME not in log_text
    assert PASSWORD not in log_text
    assert "*redacted*" in log_text
