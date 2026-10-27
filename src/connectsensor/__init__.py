"""Kingspan Sensit API."""

import importlib.metadata

from connectsensor.client import AsyncSensorClient, SensorClient
from connectsensor.const import APIVersion
from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanDBError,
    KingspanErrorCode,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)

__version__ = importlib.metadata.version("kingspan-connect-sensor")

__all__ = [
    "APIVersion",
    "AsyncSensorClient",
    "KingspanAPIError",
    "KingspanDBError",
    "KingspanErrorCode",
    "KingspanInvalidCredentialsError",
    "KingspanNoDataError",
    "KingspanTimeoutError",
    "SensorClient",
]
