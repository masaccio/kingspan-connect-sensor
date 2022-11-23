import importlib.metadata

from .client import AsyncConnectSensor, SensorClient, APIError

__version__ = importlib.metadata.version("kingspan-connect-sensor")
