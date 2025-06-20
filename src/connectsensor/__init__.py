import importlib.metadata

from connectsensor.client import AsyncSensorClient, SensorClient  # noqa: F401
from connectsensor.exceptions import APIError, DBError  # noqa: F401

__version__ = importlib.metadata.version("kingspan-connect-sensor")
