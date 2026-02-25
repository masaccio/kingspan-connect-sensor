import os
import re
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import httpx
import pytest
import json

from mock_data import PASSWORD, USERNAME

INVALID_LOGON_SESSION = "Authenicate_v3.invalid.json"
VALID_LOGON_SESSION = "Authenicate_v3.valid.json"
TANK_HISTORY_SESSION = "GetCallHistory_v1.json"
TEMPLATE_TANK_HISTORY_SESSION = "GetCallHistory_v1.template.json"
GET_LEVELS_SESSION = "GetLatestLevel_v3.json"


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
                    "{"
                    '            "signalmanNo": 20001000,'
                    f'            "levelPercentage": {percent},'
                    f'            "levelLitres": {level},'
                    f'            "readingDate": "{dt}",'
                    '            "levelAlert": false,'
                    '            "dropAlert": false,'
                    '            "consumptionRate": -1,'
                    '            "runOutDate": "0001-01-01T00:00:00.0000000+00:00"'
                    "},"
                )
        else:
            new_data += line + "\n"

    return new_data.encode("utf-8")


def get_mock_filename(url: str, content: str, generated=False) -> str:
    if m := re.search(r".*/(\w+)", url):
        method = m.group(1)
    else:
        msg = f"Can't extract API method from content: {url}"
        raise (ValueError(msg))

    if "Authenticate_v3" in method:
        data = json.loads(content)
        if data["password"] == PASSWORD:
            return os.path.join(f"tests/data/{method}.valid.json")
        return os.path.join(f"tests/data/{method}.invalid.json")

    if method == "GetCallHistory_v1" and generated:
        return os.path.join("tests/data/GetCallHistory_v1.template.json")

    return os.path.join(f"tests/data/{method}.json")


def get_mock_response(url: str, mock_data: bytes, generated=False) -> httpx.Response:
    if "GetCallHistory_v1" in mock_data.decode() and generated:
        mock_data = generate_history_data(mock_data)

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    request = httpx.Request("POST", url)
    return httpx.Response(200, content=mock_data, request=request, headers=headers)


@pytest.fixture
def mock_sync_httpx_post(request, mocker):
    """Mock httpx.Client.post method to return content from a file."""

    def mock_post(url, *args, **kwargs):
        mock_filename = get_mock_filename(url, kwargs["content"])

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)

        return get_mock_response(url, mock_response)

    def mock_generated_post(url, *args, **kwargs):
        mock_filename = get_mock_filename(kwargs["content"], generated=True)

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
