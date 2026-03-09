from datetime import datetime
from typing import TypeAlias

from _typeshed import Incomplete

API_SERVER: str
API_PORT: int
API_BASE_URL: Incomplete
HTTP_UNAUTHORIZED: int
TOKEN: str

APIResponseValue: TypeAlias = (
    str | int | datetime | list[APIResponseValue] | dict[str, APIResponseValue]
)
APIRequest: TypeAlias = dict[str, APIResponseValue]
APIResponse: TypeAlias = dict[str, APIResponseValue]
