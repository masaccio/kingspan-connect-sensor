"""Pytest fixtures and mock helpers for connectsensor tests."""

from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import aiofiles
import httpx
import pytest

from tests.mock_data import PASSWORD

if TYPE_CHECKING:
    from collections.abc import Generator


def tank_history_xml(percent: int, reading_date: datetime, level: int) -> str:
    """Build a single XML APILevel history element."""
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


def tank_history_json(percent: int, reading_date: datetime, level: int) -> str:
    """Build a single JSON level history entry."""
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
        "        }"
    )


def generate_history_data(data: bytes) -> bytes:
    """Populate template XML or JSON history payloads with generated records."""
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
                reading_date = datetime.now(tz=UTC).replace(tzinfo=None) - timedelta(days=n_days)
                if mode == "xml":
                    new_lines.append(tank_history_xml(percent, reading_date, level))
                else:
                    new_lines.append(tank_history_json(percent, reading_date, level))
            new_data += line + "\n" + "\n,".join(new_lines) + "\n"
        else:
            new_data += line + "\n"

    return new_data.encode("utf-8")


def get_mock_filename(
    url: str,
    content: str | bytes | None,
    *,
    generated: bool = False,
) -> str:
    """Resolve the mock response filename for a given request URL and payload."""
    text = content.decode() if isinstance(content, bytes) else (content or "")

    if text and (m := re.search(r"<(soap:Body|soap-env:Body)>\s*<(\w+)", text)):
        method = m.group(2)
    elif m := re.search(r".*/(\w+)", url):
        method = m.group(1)
    else:
        msg = f"Can't extract test method : url={url}, content={text}"
        raise ValueError(msg)

    if method == "SoapMobileAPPAuthenicate_v3":
        suffix = "valid" if f"<password>{PASSWORD}</password>" in text else "invalid"
        filename = f"{method}.{suffix}.xml"
    elif method == "SoapMobileAPPGetCallHistory_v1" and generated:
        filename = "SoapMobileAPPGetCallHistory_v1.template.xml"
    elif method.startswith("Soap"):
        filename = f"{method}.xml"
    elif "Authenticate_v3" in method:
        data = json.loads(text)
        suffix = "valid" if data["password"] == PASSWORD else "invalid"
        filename = f"{method}.{suffix}.json"
    elif "GetCallHistory_v1" in method and generated:
        filename = "GetCallHistory_v1_Async.template.json"
    else:
        filename = f"{method}.json"

    return os.path.join("tests/data", filename)


def get_mock_response(url: str, mock_data: bytes, *, generated: bool = False) -> httpx.Response:
    """Create a mock httpx.Response for the given URL and payload bytes."""
    if "GetCallHistory_v1" in url and generated:
        mock_data = generate_history_data(mock_data)

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    request = httpx.Request("POST", url)
    return httpx.Response(200, content=mock_data, request=request, headers=headers)


@pytest.fixture
def mock_wsdl() -> Generator[None]:
    """Mock Zeep WSDL loading from a local file."""
    wsdl_filename = "tests/data/connectsensor.wsdl"
    with open(wsdl_filename, "rb") as f:
        mock_response = f.read()

    with patch("zeep.transports.Transport.load", return_value=mock_response):
        yield


@pytest.fixture
def mock_sync_httpx_post(request: pytest.FixtureRequest) -> Generator[Mock]:
    """Mock httpx.Client.post method to return content from a file."""

    def mock_post(url: str, *_args: Any, **kwargs: Any) -> httpx.Response:
        content = kwargs.get("content") or kwargs.get("data")
        mock_filename = get_mock_filename(url, content)

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError as exc:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg) from exc

        return get_mock_response(url, mock_response)

    def mock_generated_post(url: str, *_args: Any, **kwargs: Any) -> httpx.Response:
        content = kwargs.get("content") or kwargs.get("data")
        mock_filename = get_mock_filename(url, content, generated=True)

        try:
            with open(mock_filename, "rb") as f:
                mock_response = f.read()
        except FileNotFoundError as exc:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg) from exc

        return get_mock_response(url, mock_response, generated=True)

    generate_history = hasattr(request, "param")

    with patch("httpx.Client.post", new_callable=Mock) as mock_client:
        if generate_history:
            mock_client.side_effect = mock_generated_post
        else:
            mock_client.side_effect = mock_post
        yield mock_client


@pytest.fixture
def mock_async_httpx_post(request: pytest.FixtureRequest) -> Generator[AsyncMock]:
    """Mock httpx.AsyncClient.post method to return content from a file."""

    async def mock_post(url: str, *_args: Any, **kwargs: Any) -> httpx.Response:
        content = kwargs.get("content") or kwargs.get("data")
        mock_filename = get_mock_filename(url, content)

        try:
            async with aiofiles.open(mock_filename, "rb") as f:
                mock_response = await f.read()
        except FileNotFoundError as exc:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg) from exc

        return get_mock_response(url, mock_response)

    async def mock_generated_post(url: str, *_args: Any, **kwargs: Any) -> httpx.Response:
        content = kwargs.get("content") or kwargs.get("data")
        mock_filename = get_mock_filename(url, content, generated=True)

        try:
            async with aiofiles.open(mock_filename, "rb") as f:
                mock_response = await f.read()
        except FileNotFoundError as exc:
            msg = f"Mock file not found: {mock_filename}"
            raise RuntimeError(msg) from exc

        return get_mock_response(url, mock_response, generated=True)

    generate_history = hasattr(request, "param") and request.param

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_client:
        if generate_history:
            mock_client.side_effect = mock_generated_post
        else:
            mock_client.side_effect = mock_post
        yield mock_client
