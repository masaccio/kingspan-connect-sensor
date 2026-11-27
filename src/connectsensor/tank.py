"""Tank class for Connect Sensor API."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from connectsensor.analysis import TankHistoryPoint
    from connectsensor.client import AsyncSensorClient, SensorClient
    from connectsensor.models import LatestLevelPayload


class _BaseTank:
    """Base class for Tanks."""

    def __init__(self, signalman_no: str) -> None:
        """Initialize a Tank instance."""
        self._signalman_no = signalman_no
        self._data: LatestLevelPayload | None = None

    @property
    def serial_number(self) -> str:
        """Return the serial number of the tank."""
        return self._signalman_no

    def clear_cache(self) -> None:
        """Clear the cached tank data to force a network refresh on next access."""
        self._data = None


class Tank(_BaseTank):
    """Synchronous Tank class."""

    def __init__(self, client: SensorClient, signalman_no: str) -> None:
        """Initialize a synchronous Tank instance."""
        super().__init__(signalman_no)
        self._client = client

    def _get_data(self) -> LatestLevelPayload:
        """Fetch and cache the latest tank data if not already cached."""
        if self._data is None:
            self._data = self._client._get_latest_level(self._signalman_no)  # noqa: SLF001 # pylint: disable=protected-access
        return self._data

    @property
    def level(self) -> int:
        """Return the oil level in the tank in litres."""
        return self._get_data().level_litres

    @property
    def model(self) -> str:
        """Return the model of the tank."""
        return self._get_data().model

    @property
    def name(self) -> str:
        """Return the name of the tank."""
        return self._get_data().name

    @property
    def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        return self._get_data().capacity

    @property
    def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        return self._get_data().reading_date

    def history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[TankHistoryPoint]:
        """Return the history of the tank readings as a list of TankHistoryPoint."""
        return self._client._get_history(  # noqa: SLF001 # pylint: disable=protected-access
            self._signalman_no,
            start_date,
            end_date,
        )


class AsyncTank(_BaseTank):
    """Asynchronous Tank class."""

    def __init__(self, client: AsyncSensorClient, signalman_no: str) -> None:
        """Initialize an asynchronous Tank instance."""
        super().__init__(signalman_no)
        self._client = client

    async def _get_data(self) -> LatestLevelPayload:
        """Fetch and cache the latest tank data if not already cached."""
        if self._data is None:
            self._data = await self._client._get_latest_level(self._signalman_no)  # noqa: SLF001 # pylint: disable=protected-access
        return self._data

    @property
    async def level(self) -> int:
        """Return the oil level in the tank in litres."""
        return (await self._get_data()).level_litres

    @property
    async def model(self) -> str:
        """Return the model of the tank."""
        return (await self._get_data()).model

    @property
    async def name(self) -> str:
        """Return the name of the tank."""
        return (await self._get_data()).name

    @property
    async def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        return (await self._get_data()).capacity

    @property
    async def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        return (await self._get_data()).reading_date

    async def history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[TankHistoryPoint]:
        """Return the history of the tank readings as a list of TankHistoryPoint."""
        return await self._client._get_history(  # noqa: SLF001 # pylint: disable=protected-access
            self._signalman_no,
            start_date,
            end_date,
        )
