import pytest
import os

import aiofiles

import json
from glob import glob
import re
from datetime import timedelta, datetime
from time import strptime
from unittest.mock import patch, MagicMock


def read_json_files():
    cache = {}
    for filename in glob("tests/data/*.json"):
        api = re.sub(".*/(\w+)\..*", "\\1", filename)
        with open(filename) as fh:
            obj = json.load(fh)
            body = obj["Envelope"]["Body"]
            cache[os.path.basename(filename)] = body[f"{api}Response"][f"{api}Result"]
    return cache


TEST_DATA = read_json_files()


async def async_read_test_json(filename, api):
    test_filename = os.path.join("tests/data", filename)
    async with aiofiles.open(test_filename, mode="r") as fh:
        obj = json.load(fh)
        return obj["Envelope"]["Body"][f"{api}Response"][f"{api}Result"]


def read_test_json(filename, api):
    test_filename = os.path.join("tests/data", filename)
    with open(test_filename) as fh:
        obj = json.load(fh)
        return obj["Envelope"]["Body"][f"{api}Response"][f"{api}Result"]


def generate_history_data(obj):
    for i in range(10):
        percent = 100 - i * 10
        level = int(2000 * (percent / 100))
        n_days = 50 - i * 5
        dt = datetime.now() - timedelta(days=n_days)
        obj["Levels"]["APILevel"].append(
            {
                "SignalmanNo": "20001000",
                "LevelPercentage": percent,
                "LevelLitres": level,
                "ReadingDate": dt,
                "LevelAlert": False,
                "DropAlert": False,
                "ConsumptionRate": -1,
                "RunOutDate": datetime(1, 1, 1, 0, 0, 0),
            }
        )
    return obj


def Mocked_SoapMobileAPPAuthenicate_v3(**kwargs):
    if kwargs["emailaddress"] is None or kwargs["emailaddress"] != "test@example.com":
        json_filename = "SoapMobileAPPAuthenicate_v3.invalid.json"
    elif kwargs["password"] is None or kwargs["password"] != "s3cret":
        json_filename = "SoapMobileAPPAuthenicate_v3.invalid.json"
    else:
        json_filename = "SoapMobileAPPAuthenicate_v3.valid.json"
    return TEST_DATA[json_filename]


def Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs):
    return TEST_DATA["SoapMobileAPPGetLatestLevel_v3.json"]


def Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs):
    obj = TEST_DATA["SoapMobileAPPGetCallHistory_v1.json"]
    for level in obj["Levels"]["APILevel"]:
        level["ReadingDate"] = datetime(
            *strptime(level["ReadingDate"], "%Y-%m-%dT%H:%M:%S.000")[:6]
        )
    return obj


async def Async_Mocked_SoapMobileAPPAuthenicate_v3(**kwargs):
    return Mocked_SoapMobileAPPAuthenicate_v3(**kwargs)


async def Async_Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs):
    return Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs)


async def Async_Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs):
    return Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs)


@pytest.fixture(name="mock_zeep")
def mock_zeep_fixture():
    with patch("connectsensor.client.SoapClient") as mock_zeep:
        zeep_instance = MagicMock()
        mock_zeep.return_value = zeep_instance

        zeep_instance.service.SoapMobileAPPAuthenicate_v3.side_effect = (
            Mocked_SoapMobileAPPAuthenicate_v3
        )
        zeep_instance.service.SoapMobileAPPGetLatestLevel_v3.side_effect = (
            Mocked_SoapMobileAPPGetLatestLevel_v3
        )
        zeep_instance.service.SoapMobileAPPGetCallHistory_v1.side_effect = (
            Mocked_SoapMobileAPPGetCallHistory_v1
        )

        yield mock_zeep


@pytest.fixture(name="async_mock_zeep")
def async_mock_zeep_fixture():
    with patch("connectsensor.client.AsyncSoapClient") as mock_zeep:
        zeep_instance = MagicMock()
        mock_zeep.return_value = zeep_instance

        zeep_instance.service.SoapMobileAPPAuthenicate_v3.side_effect = (
            Async_Mocked_SoapMobileAPPAuthenicate_v3
        )
        zeep_instance.service.SoapMobileAPPGetLatestLevel_v3.side_effect = (
            Async_Mocked_SoapMobileAPPGetLatestLevel_v3
        )
        zeep_instance.service.SoapMobileAPPGetCallHistory_v1.side_effect = (
            Async_Mocked_SoapMobileAPPGetCallHistory_v1
        )

        yield mock_zeep
