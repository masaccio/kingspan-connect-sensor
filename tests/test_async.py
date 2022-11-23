import logging
import os
import pytest
import zeep.transports

from requests import Response
from unittest.mock import patch

from mock_data import VALID_STATUS, USERNAME, PASSWORD
from mock_requests import MockResponse, mock_load_remote_data, async_mock_post

from connectsensor import __version__, AsyncConnectSensor


@pytest.mark.asyncio
async def test_status(aiohttp_client, loop):
    logging.basicConfig(level=logging.DEBUG)

    with patch.object(
        zeep.transports.AsyncTransport,
        "_load_remote_data",
        side_effect=mock_load_remote_data,
    ) as mock_get, patch.object(
        zeep.transports.AsyncTransport,
        "post_xml",
        side_effect=async_mock_post,
    ) as mock_post:
        async with AsyncConnectSensor() as client:
            await client.login(USERNAME, PASSWORD)
            tank_status = await client.tanks()
            tank_level = tank_status[0].level()
