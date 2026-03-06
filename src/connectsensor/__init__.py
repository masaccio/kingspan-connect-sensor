"""Kingspan Sensit API."""

import importlib.metadata

from connectsensor.client import AsyncSensorClient, SensorClient  # noqa: F401
from connectsensor.const import APIVersion
from connectsensor.exceptions import *  # noqa: F403

__version__ = importlib.metadata.version("kingspan-connect-sensor")
