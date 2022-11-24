import importlib.metadata

from .client import AsyncSensorClient, SensorClient, APIError

__version__ = importlib.metadata.version("kingspan-connect-sensor")
