import importlib.metadata

from .client import SensorClient, APIError

__version__ = importlib.metadata.version("kingspan-connect-sensor")
