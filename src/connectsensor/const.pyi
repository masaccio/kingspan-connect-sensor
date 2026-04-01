from _typeshed import Incomplete
from enum import IntEnum
from typing import TypeAlias

API_SERVER: str
API_PORT: int
API_BASE_URL: Incomplete
DEFAULT_SERVER: str
WSDL_PATH: str
WSDL_URL: Incomplete
SOAP_NS_PREFIX: str

class APIVersion(IntEnum):
    CONNECT_V1 = ...
    KNECT_V1 = ...

DEFAULT_API_VERSION: Incomplete
HTTP_UNAUTHORIZED: int
TOKEN: str
APIResponseValue: TypeAlias
APIRequest: TypeAlias = dict[str, APIResponseValue]
APIResponse: TypeAlias = dict[str, APIResponseValue]
