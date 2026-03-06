import json
import os
import re
from datetime import datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import httpx
import pytest

from mock_data import PASSWORD


def tank_history_xml(percent: int, reading_date: datetime, level: int):
    return (
        "          <APILevel>"
        "            <SignalmanNo>20001000</SignalmanNo>"
        f"            <LevelPercentage>{percent}</LevelPercentage>"
        f"            <LevelLitres>{level}</LevelLitres>"
        f"            <ReadingDate>{reading_date}</ReadingDate>"
        "            <LevelAlert>false</LevelAlert>"
        "            <DropAlert>false</DropAlert>"
        "            <ConsumptionRate>-1</ConsumptionRate>"
        "            <RunOutDate>0001-01-01T00:00:00</RunOutDate>"
        "          </APILevel>"
    )


def tank_history_json(percent: int, reading_date: datetime, level: int):
    return (
        "        {\n"
        '            "signalmanNo": 20001000,\n'
        f'            "levelPercentage": {percent},\n'
        f'            "levelLitres": {level},\n'
        f'            "readingDate": "{reading_date}",\n'
        '            "levelAlert": false,\n'
        '            "dropAlert": false,\n'
        '            "consumptionRate": -1,\n'
        '            "runOutDate": "0001-01-01T00:00:00.0000000+00:00"\n'
        f"        }}"
    )


def generate_history_data(data: bytes) -> bytes:
    new_data = ""
    for line in data.decode().splitlines():
        if '"levels":' in line:
            mode = "json"
        elif "<Levels>" in line:
            mode = "xml"
        else:
            mode = None
        if mode is not None:
            new_lines = []
            for i in range(10):
                percent = 100 - i * 10
                level = int(2000 * (percent / 100))
                n_days = 50 - i * 5
                reading_date = datetime.now() - timedelta(days=n_days)
                if mode == "xml":
                    new_lines.append(tank_history_xml(percent, reading_date, level))
                else:
                    new_lines.append(tank_history_json(percent, reading_date, level))
            new_data += line + "\n" + "\n,".join(new_lines) + "\n"
        else:
            new_data += line + "\n"

    return new_data.encode("utf-8")


def get_mock_filename(url: str, content: str | bytes, generated=False) -> str:
    content = content.decode() if isinstance(content, bytes) else cast("str", content)

    if content is not None and (
        m := re.search(r"<(soap:Body|soap-env:Body)>\s*<(\w+)", content)
    ):
        method = m.group(2)
    elif m := re.search(r".*/(\w+)", url):
        method = m.group(1)
    else:
        msg = f"Can't extract test method : url={url}, content={content}"
        raise (ValueError(msg))

    if method == "SoapMobileAPPAuthenicate_v3":
        if f"<password>{PASSWORD}</password>" in content:
            return os.path.join(f"tests/data/{method}.valid.xml")
        return os.path.join(f"tests/data/{method}.invalid.xml")

    if method == "SoapMobileAPPGetCallHistory_v1" and generated:
        return os.path.join("tests/data/SoapMobileAPPGetCallHistory_v1.template.xml")

    if "SOAP" in method:
        return os.path.join(f"tests/data/{method}.xml")

    if "Authenticate_v3" in method:
        data = json.loads(content)
        if data["password"] == PASSWORD:
            return os.path.join(f"tests/data/{method}.valid.json")
        return os.path.join(f"tests/data/{method}.invalid.json")

    if "GetCallHistory_v1" in method and generated:
        return os.path.join("tests/data/GetCallHistory_v1_Async.template.json")

    return os.path.join(f"tests/data/{method}.json")


def get_mock_response(url: str, mock_data: bytes, generated=False) -> httpx.Response:
    if "GetCallHistory_v1" in url and generated:
        mock_data = generate_history_data(mock_data)

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    request = httpx.Request("POST", url)
    return httpx.Response(200, content=mock_data, request=request, headers=headers)


@pytest.fixture
def mock_sync_httpx_post(request):
    """Mock httpx.Client.post method to return content from a file."""

    def mock_post(url, *args, **kwargs):
        if "content" in kwargs:
            content = kwargs["content"]
        elif "data" in kwargs:
            content = kwargs["data"]
        else:
            content = None
        mock_filename = get_mock_filename(url, content)

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)  # noqa: B904

        return get_mock_response(url, mock_response)

    def mock_generated_post(url, *args, **kwargs):
        content = kwargs["content"] if "content" in kwargs else kwargs["data"]
        mock_filename = get_mock_filename(url, content, generated=True)

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)  # noqa: B904

        return get_mock_response(url, mock_response, generated=True)

    generate_history = hasattr(request, "param")

    with patch("httpx.Client.post", new_callable=Mock) as mock_client:
        if generate_history:
            mock_client.side_effect = mock_generated_post
        else:
            mock_client.side_effect = mock_post
        yield mock_client


@pytest.fixture
def mock_async_httpx_post():
    """Mock httpx.AsyncClient.post method to return content from a file."""

    async def mock_post(url, *args, **kwargs):
        content = kwargs["content"] if "content" in kwargs else kwargs["data"]
        mock_filename = get_mock_filename(url, content)

        try:
            async with aiofiles.open(mock_filename, "rb") as f:
                mock_response = await f.read()
        except FileNotFoundError:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg)  # noqa: B904

        return get_mock_response(url, mock_response)

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_client:
        mock_client.side_effect = mock_post
        yield mock_client
