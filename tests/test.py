import os
import re
import requests
import pandas as pd
import sys
from unittest import TestCase, main, mock
from datetime import datetime

cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cwd + "/../")

from connectsensor import SensorClient, APIError


def xml_match(xml, key):
    m = re.search(f"<{key}>(.*)</{key}>", xml)
    if m is None or m.group(1) is None:
        return None
    else:
        return m.group(1)


def read_test_xml(filename):
    test_filename = os.path.join("tests", filename)
    with open(test_filename) as fh:
        xml = fh.read()
        xml = bytes(bytearray(xml, encoding="utf-8"))
        return xml
    fh.close()


class MockResponse:
    def __init__(self, content, status_code):
        self.status_code = status_code
        self.content = content
        self.headers = {}

    def raise_for_status(self):
        if self.status_code != 200:
            raise


def mock_get(*args, **kwargs):
    if args[0].endswith("WSDL"):
        xml = read_test_xml("connectsensor.wsdl")
        return MockResponse(xml, 200)
    else:
        return MockResponse("", 404)


def mock_post(*args, **kwargs):
    if args[0].startswith("https://www.connectsensor.com/"):
        soap_action = kwargs["headers"]["SOAPAction"]
        xml = kwargs["data"].decode("ascii")
        if "SoapMobileAPPAuthenicate_v3" in soap_action:
            email = xml_match(xml, "emailaddress")
            password = xml_match(xml, "password")
            if email is None or email != "test@example.com":
                xml_filename = "SoapMobileAPPAuthenicate_v3.invalid.xml"
            elif password is None or password != "s3cret":
                xml_filename = "SoapMobileAPPAuthenicate_v3.invalid.xml"
            else:
                xml_filename = "SoapMobileAPPAuthenicate_v3.valid.xml"
            xml = read_test_xml(xml_filename)
            return MockResponse(xml, 200)
        elif "SoapMobileAPPGetLatestLevel_v3" in soap_action:
            xml = read_test_xml("SoapMobileAPPGetLatestLevel_v3.xml")
            return MockResponse(xml, 200)
        elif "SoapMobileAPPGetCallHistory_v1" in soap_action:
            xml = read_test_xml("SoapMobileAPPGetCallHistory_v1.xml")
            return MockResponse(xml, 200)
    else:
        return MockResponse("", 404)


class SensorClientTests(TestCase):
    @mock.patch("requests.sessions.Session.post", side_effect=mock_post)
    @mock.patch("requests.sessions.Session.get", side_effect=mock_get)
    def test_valid_login(self, mock_get, mock_post):
        client = SensorClient()
        mock_get.assert_called_with(
            "https://www.connectsensor.com/soap/MobileApp.asmx?WSDL", timeout=300
        )

        client.login("test@example.com", "s3cret")
        mock_post.assert_called()

        tanks = client.tanks()
        self.assertEqual(tanks[0].name(), "TestTank")
        self.assertEqual(tanks[0].capacity(), "2000")
        self.assertEqual(tanks[0].serial_number(), "20001000")
        self.assertEqual(tanks[0].model(), "TestModel")
        self.assertEqual(mock_post.call_count, 2)

    @mock.patch("requests.sessions.Session.post", side_effect=mock_post)
    @mock.patch("requests.sessions.Session.get", side_effect=mock_get)
    def test_invalid_login(self, mock_get, mock_post):
        err_msg = ""
        try:
            client = SensorClient()
            client.login("invalid", "invalid")
        except APIError as e:
            err_msg = str(e)
        self.assertEqual(err_msg, "Authentication Failed, Invalid Login")

    @mock.patch("requests.sessions.Session.post", side_effect=mock_post)
    @mock.patch("requests.sessions.Session.get", side_effect=mock_get)
    def test_levels(self, mock_get, mock_post):
        client = SensorClient()
        client.login("test@example.com", "s3cret")
        tanks = client.tanks()
        levels = tanks[0].level()
        self.assertEqual(levels["SignalmanNo"], 20001000)
        self.assertEqual(levels["LevelLitres"], 1000)
        self.assertEqual(levels["LevelLitres"], 1000)

        history = tanks[0].history()

        self.assertEqual(mock_post.call_count, 3)


if __name__ == "__main__":
    main()
