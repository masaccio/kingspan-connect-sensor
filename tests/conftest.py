import pytest
import pytest_asyncio
import os

import json
from glob import glob
import re
from datetime import timedelta, datetime
from time import strptime
from unittest.mock import patch, MagicMock

INVALID_LOGON_SESSION = "SoapMobileAPPAuthenicate_v3.invalid.json"
VALID_LOGON_SESSION = "SoapMobileAPPAuthenicate_v3.valid.json"
TANK_HISTORY_SESSION = "SoapMobileAPPGetCallHistory_v1.json"
TEMPLATE_TANK_HISTORY_SESSION = "SoapMobileAPPGetCallHistory_v1.template.json"
GET_LEVELS_SESSION = "SoapMobileAPPGetLatestLevel_v3.json"


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


def patch_datetime(obj):
    obj["ReadingDate"] = datetime.strptime(obj["ReadingDate"], "%Y-%m-%dT%H:%M:%S.%f")


def patch_levels_datetimes(obj):
    for level in obj["Levels"]["APILevel"]:
        patch_datetime(level)


def read_json_files():
    cache = {}
    for filename in glob("tests/data/*.json"):
        api = re.sub(".*/(\w+)\..*", "\\1", filename)
        with open(filename) as fh:
            obj = json.load(fh)
            body = obj["Envelope"]["Body"]
            cache[os.path.basename(filename)] = body[f"{api}Response"][f"{api}Result"]

    patch_datetime(cache[GET_LEVELS_SESSION]["Level"])
    patch_levels_datetimes(cache[TANK_HISTORY_SESSION])
    generate_history_data(cache[TEMPLATE_TANK_HISTORY_SESSION])

    return cache


TEST_DATA = read_json_files()


def Mocked_SoapMobileAPPAuthenicate_v3(**kwargs):
    if kwargs["emailaddress"] is None or kwargs["emailaddress"] != "test@example.com":
        json_filename = INVALID_LOGON_SESSION
    elif kwargs["password"] is None or kwargs["password"] != "s3cret":
        json_filename = INVALID_LOGON_SESSION
    else:
        json_filename = VALID_LOGON_SESSION
    return TEST_DATA[json_filename]


def Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs):
    return TEST_DATA[GET_LEVELS_SESSION]


def Mocked_Generated_SoapMobileAPPGetCallHistory_v1(**kwargs):
    return TEST_DATA[TEMPLATE_TANK_HISTORY_SESSION]


def Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs):
    return TEST_DATA[TANK_HISTORY_SESSION]


async def Async_Mocked_SoapMobileAPPAuthenicate_v3(**kwargs):
    return Mocked_SoapMobileAPPAuthenicate_v3(**kwargs)


async def Async_Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs):
    return Mocked_SoapMobileAPPGetLatestLevel_v3(**kwargs)


async def Async_Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs):
    return Mocked_SoapMobileAPPGetCallHistory_v1(**kwargs)


@pytest.fixture
def mock_zeep(request):
    generate = hasattr(request, "param")
    with patch("connectsensor.client.SoapClient") as mock_zeep:
        zeep_instance = MagicMock()
        mock_zeep.return_value = zeep_instance

        zeep_instance.service.SoapMobileAPPAuthenicate_v3.side_effect = (
            Mocked_SoapMobileAPPAuthenicate_v3
        )
        zeep_instance.service.SoapMobileAPPGetLatestLevel_v3.side_effect = (
            Mocked_SoapMobileAPPGetLatestLevel_v3
        )
        if generate:
            zeep_instance.service.SoapMobileAPPGetCallHistory_v1.side_effect = (
                Mocked_Generated_SoapMobileAPPGetCallHistory_v1
            )
        else:
            zeep_instance.service.SoapMobileAPPGetCallHistory_v1.side_effect = (
                Mocked_SoapMobileAPPGetCallHistory_v1
            )

        yield mock_zeep


@pytest_asyncio.fixture
def async_mock_zeep():
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
