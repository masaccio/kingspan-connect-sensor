import asyncio
import aiofiles
import os
import re

from datetime import datetime, timedelta
from zeep.wsdl.utils import etree_to_string


def xml_match(xml, key):
    m = re.search(f"<{key}>(.*)</{key}>", xml)
    if m is None or m.group(1) is None:
        return None
    else:
        return m.group(1)


def read_test_xml(filename):
    test_filename = os.path.join("tests/data", filename)
    with open(test_filename) as fh:
        xml = fh.read()
        xml = bytes(bytearray(xml, encoding="utf-8"))
        return xml
    fh.close()


async def async_read_test_xml(filename):
    test_filename = os.path.join("tests/data", filename)
    async with aiofiles.open(test_filename, mode="r") as fh:
        xml = await fh.read()
    xml = bytes(bytearray(xml, encoding="utf-8"))
    return xml


class MockResponse:
    def __init__(self, content, status_code):
        self.status_code = status_code
        self.content = content
        self.encoding = None
        self.headers = {}

    def raise_for_status(self):
        if self.status_code != 200:
            raise

    def read(self):
        return self.content


def generate_history_xml():
    xml = ""
    with open("tests/data/SoapMobileAPPGetCallHistory_v1.template") as fh:
        for line in fh.readlines():
            if "{{LEVELS}}" in line:
                for i in range(10):
                    percent = 100 - i * 10
                    level = int(2000 * (percent / 100))
                    n_days = 50 - i * 5
                    dt = datetime.now() - timedelta(days=n_days)
                    xml += f"<APILevel>\n"
                    xml += "<SignalmanNo>20001000</SignalmanNo>\n"
                    xml += f"<LevelPercentage>{percent}</LevelPercentage>\n"
                    xml += f"<LevelLitres>{level}</LevelLitres>\n"
                    xml += f"<ReadingDate>{dt.isoformat()}</ReadingDate>\n"
                    xml += "<LevelAlert>false</LevelAlert>\n"
                    xml += "<DropAlert>false</DropAlert>\n"
                    xml += "<ConsumptionRate>-1</ConsumptionRate>\n"
                    xml += "<RunOutDate>0001-01-01T00:00:00</RunOutDate>\n"
                    xml += f"</APILevel>\n"
            else:
                xml += line
    return bytes(bytearray(xml, encoding="utf-8"))


def mock_get(*args, **kwargs):
    if args[0].endswith("WSDL"):
        xml = read_test_xml("connectsensor.wsdl")
        return MockResponse(xml, 200)
    else:
        return MockResponse("", 404)


def mock_load_remote_data(url):
    xml = read_test_xml("connectsensor.wsdl")
    return xml


def mock_post(xml, soap_action):
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


def mock_requests_post(*args, **kwargs):
    if args[0].startswith("https://www.connectsensor.com/"):
        soap_action = kwargs["headers"]["SOAPAction"]
        xml = kwargs["data"].decode("ascii")
        return mock_post(xml, soap_action)
    else:
        return MockResponse("", 404)


def mock_requests_post_generate(*args, **kwargs):
    if args[0].startswith("https://www.connectsensor.com/"):
        soap_action = kwargs["headers"]["SOAPAction"]
        xml = kwargs["data"].decode("ascii")
        if "SoapMobileAPPGetCallHistory_v1" in soap_action:
            xml = generate_history_xml()
            return MockResponse(xml, 200)
        else:
            return mock_post(xml, soap_action)
    else:
        return MockResponse("", 404)


def mock_post_xml(address, envelope, headers):
    if address.startswith("https://www.connectsensor.com/"):
        soap_action = headers["SOAPAction"]
        xml = str(etree_to_string(envelope))
        return mock_post(xml, soap_action)
    else:
        return MockResponse("", 404)


async def async_mock_post_xml(address, envelope, headers):
    if address.startswith("https://www.connectsensor.com/"):
        soap_action = headers["SOAPAction"]
        xml = str(etree_to_string(envelope))
        if "SoapMobileAPPAuthenicate_v3" in soap_action:
            email = xml_match(xml, "emailaddress")
            password = xml_match(xml, "password")
            if email is None or email != "test@example.com":
                xml_filename = "SoapMobileAPPAuthenicate_v3.invalid.xml"
            elif password is None or password != "s3cret":
                xml_filename = "SoapMobileAPPAuthenicate_v3.invalid.xml"
            else:
                xml_filename = "SoapMobileAPPAuthenicate_v3.valid.xml"
            xml = await async_read_test_xml(xml_filename)
            return MockResponse(xml, 200)
        elif "SoapMobileAPPGetLatestLevel_v3" in soap_action:
            xml = await async_read_test_xml("SoapMobileAPPGetLatestLevel_v3.xml")
            return MockResponse(xml, 200)
        elif "SoapMobileAPPGetCallHistory_v1" in soap_action:
            xml = await async_read_test_xml("SoapMobileAPPGetCallHistory_v1.xml")
            return MockResponse(xml, 200)
    else:
        return MockResponse("", 404)
