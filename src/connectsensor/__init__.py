import importlib.metadata

from .client import AsyncSensorClient, SensorClient
from .exceptions import DBError, APIError

__version__ = importlib.metadata.version("kingspan-connect-sensor")
