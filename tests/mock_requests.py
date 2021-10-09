import os
import re
import requests


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


class MockResponse:
    def __init__(self, content, status_code):
        self.status_code = status_code
        self.content = content
        self.encoding = None
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
