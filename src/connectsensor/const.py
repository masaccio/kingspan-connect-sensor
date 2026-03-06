"""Constants and types shared across the package."""

from enum import IntEnum, auto
from typing import TypeAlias

# JSON API is HTTP and sends the username and password in the clear
API_SERVER = "sensorapi.connectsensor.com"
API_PORT = 8087
API_BASE_URL = f"http://{API_SERVER}:{API_PORT}"

# SOAP API
DEFAULT_SERVER = "www.connectsensor.com"
WSDL_PATH = "soap/MobileApp.asmx?WSDL"
WSDL_URL = f"https://{DEFAULT_SERVER}/{WSDL_PATH}"
SOAP_NS_PREFIX = "http://mobileapp/"


# API versions don't match what Kingspan call them as these are not obviously
# incrementing and use different servers/protocols.
class APIVersion(IntEnum):
    CONNECT_V1 = auto()
    KNECT_V1 = auto()


DEFAULT_API_VERSION = APIVersion.KNECT_V1

HTTP_UNAUTHORIZED = 401

# The JWT appears to be hard-coded into the application rather than securely returned
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJUaGVNb2JpbGVBcHAiLCJyb2xlIjoiVGhlTW9iaWxlQXBwIiwiZXhwIjoxNzg2ODk4NTM3LCJpc3MiOiJTZW5zb3JBUEkgQXV0aFNlcnZlciIsImF1ZCI6IlNlbnNvckFQSSBVc2VycyJ9.PW-NP46vP9pP5Da87KIzsN6ZWIA3vOI4XbqxHWVuTOY"  # noqa: E501, S105, cspell:disable-line

# Types for API request and response
APIResponseValue: TypeAlias = (
    str | list["APIResponseValue"] | dict[str, "APIResponseValue"]
)
APIRequest: TypeAlias = dict[str, APIResponseValue]
APIResponse: TypeAlias = dict[str, APIResponseValue]
