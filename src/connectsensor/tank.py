"""Tank class for Connect Sensor API."""

from async_property import async_property
from datetime import datetime


class BaseTank:
    """Base class for Tanks."""

    def __init__(self, client: object, signalman_no: str) -> None:
        """Initialize a Tank instance."""
        self._client = client
        self._signalman_no = signalman_no
        self._level_data = None

    def _unpack_tank_data(self, response) -> None:
        self._level_data = response["level"]
        self._tank_info = {x["name"]: x["value"] for x in response["tankInfo"]}

    def _transform_history_data(self, data: dict[str, list[dict]]) -> list[dict]:
        """Transform raw tank history data into a list of dicts."""
        return [
            {
                "reading_date": datetime.fromisoformat(x["readingDate"]),
                "level_percent": x["levelPercentage"],
                "level_litres": x["levelLitres"],
            }
            for x in data
        ]


class Tank(BaseTank):
    """Synchronous Tank class."""

    @property
    def level(self) -> int:
        """Return the oil level in the tank in litres."""
        self._cache_tank_data()
        return int(self._level_data["levelLitres"])

    @property
    def serial_number(self) -> str:
        """Return the serial number of the tank."""
        self._cache_tank_data()
        return self._tank_info["Signalman No"]

    @property
    def model(self) -> str:
        """Return the model of the tank."""
        self._cache_tank_data()
        return self._tank_info["Model"]

    @property
    def name(self) -> str:
        """Return the name of the tank."""
        self._cache_tank_data()
        return self._tank_info["Tank Name"]

    @property
    def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        self._cache_tank_data()
        return int(self._tank_info["Tank Capacity(L)"])

    @property
    def last_read(self) -> str:
        """Return the last read date of the tank as a datetime object."""
        self._cache_tank_data()
        return self._level_data["readingDate"]

    @property
    def history(self):
        """Return the history of the tank readings as a list of dicts."""
        history_data = self._client._get_history(self._signalman_no)
        return self._transform_history_data(history_data)

    def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            response = self._client._get_latest_level(self._signalman_no)
            self._unpack_tank_data(response)


class AsyncTank:
    """Asynchronous Tank class."""

    @async_property
    async def level(self) -> int:
        """Return the oil level in the tank in litres."""
        await self._cache_tank_data()
        return int(self._level_data["LevelLitres"])

    @async_property
    async def serial_number(self) -> str:
        """Return the serial number of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Serial No"]

    @async_property
    async def model(self) -> str:
        """Return the model of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Model"]

    @async_property
    async def name(self) -> str:
        """Return the name of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Tank Name"]

    @async_property
    async def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        await self._cache_tank_data()
        return int(self._tank_info["Tank Capacity(L)"])

    @async_property
    async def last_read(self) -> str:
        """Return the last read date of the tank as a datetime object."""
        await self._cache_tank_data()
        return self._level_data["ReadingDate"]

    @async_property
    async def history(self):
        """Return the history of the tank readings as a list of dicts."""
        history_data = await self._client._get_history(self._signalman_no)
        return self._transform_history_data(history_data)

    async def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            response = await self._client._get_latest_level(self._signalman_no)
            self._unpack_tank_data(self, response)
