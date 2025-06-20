import os
import re
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import httpx
import pytest
from zeep.exceptions import Fault

from mock_data import PASSWORD, USERNAME

INVALID_LOGON_SESSION = "SoapMobileAPPAuthenicate_v3.invalid.xml"
VALID_LOGON_SESSION = "SoapMobileAPPAuthenicate_v3.valid.xml"
TANK_HISTORY_SESSION = "SoapMobileAPPGetCallHistory_v1.xml"
TEMPLATE_TANK_HISTORY_SESSION = "SoapMobileAPPGetCallHistory_v1.template.xml"
GET_LEVELS_SESSION = "SoapMobileAPPGetLatestLevel_v3.xml"


def generate_history_data(data: bytes) -> bytes:
    new_data = ""
    for line in data.decode().splitlines():
        if "<Levels>" in line:
            new_data += line + "\n"
            for i in range(10):
                percent = 100 - i * 10
                level = int(2000 * (percent / 100))
                n_days = 50 - i * 5
                dt = datetime.now() - timedelta(days=n_days)
                new_data += (
                    "          <APILevel>"
                    "            <SignalmanNo>20001000</SignalmanNo>"
                    f"            <LevelPercentage>{percent}</LevelPercentage>"
                    f"            <LevelLitres>{level}</LevelLitres>"
                    f"            <ReadingDate>{dt}</ReadingDate>"
                    "            <LevelAlert>false</LevelAlert>"
                    "            <DropAlert>false</DropAlert>"
                    "            <ConsumptionRate>-1</ConsumptionRate>"
                    "            <RunOutDate>0001-01-01T00:00:00</RunOutDate>"
                    "          </APILevel>"
                )
        else:
            new_data += line + "\n"

    return new_data.encode("utf-8")


def get_mock_filename(content: bytes, generated=False) -> str:
    if m := re.search(r"<(soap:Body|soap-env:Body)>\s*<(\w+)", content.decode()):
        method = m.group(2)
    else:
        msg = f"Can't extract SOAP method from content: {content}"
        raise (ValueError(msg))

    if method == "SoapMobileAPPAuthenicate_v3":
        if f"<password>{PASSWORD}</password>" in content.decode():
            return os.path.join(f"tests/data/{method}.valid.xml")
        return os.path.join(f"tests/data/{method}.invalid.xml")

    if method == "SoapMobileAPPGetCallHistory_v1" and generated:
        return os.path.join("tests/data/SoapMobileAPPGetCallHistory_v1.template.xml")

    return os.path.join(f"tests/data/{method}.xml")


def get_mock_response(url: str, mock_data: bytes, generated=False) -> httpx.Response:
    if "SoapMobileAPPGetCallHistory_v1" in mock_data.decode() and generated:
        mock_data = generate_history_data(mock_data)

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    request = httpx.Request("POST", url)
    return httpx.Response(200, content=mock_data, request=request, headers=headers)


@pytest.fixture
def mock_sync_httpx_post(request, mocker):
    """Mock httpx.Client.post method to return content from a file."""

    def mock_post(url, *args, **kwargs):
        mock_filename = get_mock_filename(kwargs["data"])

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)

        return get_mock_response(url, mock_response)

    def mock_generated_post(url, *args, **kwargs):
        mock_filename = get_mock_filename(kwargs["data"], generated=True)

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)

        return get_mock_response(url, mock_response, generated=True)

    generate_history = hasattr(request, "param")

    with patch("httpx.Client.post", new_callable=Mock) as mock_client:
        if generate_history:
            mock_client.side_effect = mock_generated_post
        else:
            mock_client.side_effect = mock_post
        yield mock_client


@pytest.fixture
def mock_async_httpx_post(mocker):
    """Mock httpx.AsyncClient.post method to return content from a file."""

    async def mock_post(url, *args, **kwargs):
        mock_filename = get_mock_filename(kwargs["content"])

        try:
            async with aiofiles.open(mock_filename, "rb") as f:
                mock_response = await f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)

        return get_mock_response(url, mock_response)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_client:
        mock_client.side_effect = mock_post
        yield mock_client
