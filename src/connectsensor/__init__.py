"""Kingspan Sensit API."""

import importlib.metadata

from connectsensor.client import AsyncSensorClient, SensorClient
from connectsensor.const import APIVersion
from connectsensor.exceptions import *  # noqa: F403

__version__ = importlib.metadata.version("kingspan-connect-sensor")

__all__ = [  # noqa: F405
    "APIVersion",
    "AsyncSensorClient",
    "KingspanAPIError",
    "KingspanDBError",
    "KingspanInvalidCredentialsError",
    "KingspanTimeoutError",
    "SensorClient",
]
