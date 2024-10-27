import importlib.metadata

from .client import AsyncSensorClient, SensorClient  # noqa: F401
from .exceptions import DBError, APIError  # noqa: F401

__version__ = importlib.metadata.version("kingspan-connect-sensor")
