from _typeshed import Incomplete
from typing import TypeAlias

API_SERVER: str
API_PORT: int
API_BASE_URL: Incomplete
HTTP_UNAUTHORIZED: int
TOKEN: str
APIResponseValue: TypeAlias
APIRequest: TypeAlias = dict[str, APIResponseValue]
APIResponse: TypeAlias = dict[str, APIResponseValue]
