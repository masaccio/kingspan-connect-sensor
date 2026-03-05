"""Tank class for Connect Sensor API."""

from datetime import datetime

from async_property import async_property

from connectsensor.const import APIResponse


class _BaseTank:
    """Base class for Tanks."""

    def __init__(self, client: object, signalman_no: str) -> None:
        """Initialize a Tank instance."""
        self._client = client
        self._signalman_no = signalman_no
        self._level_data = None

    def unpack_tank_data(self, response: APIResponse) -> None:
        self._level_data = response["level"]
        self._tank_info = {x["name"]: x["value"] for x in response["tankInfo"]}

    def property_lookup(self, obj: dict, key: str) -> str:
        """Lookup a key with either an upper or lower case first letter."""
        key_lower = key[0].lower() + key[1:]
        return obj[key_lower] if key_lower in obj else obj[key]

    def transform_history_data(self, data: APIResponse) -> APIResponse:
        """Transform raw tank history data into a list of dicts."""
        return [
            {
                "reading_date": datetime.fromisoformat(
                    self.property_lookup(x, "ReadingDate")
                ),
                "level_percent": self.property_lookup(x, "LevelPercentage"),
                "level_litres": self.property_lookup(x, "LevelLitres"),
            }
            for x in data
        ]


class Tank(_BaseTank):
    """Synchronous Tank class."""

    @property
    def level(self) -> int:
        """Return the oil level in the tank in litres."""
        self._cache_tank_data()
        return int(self.property_lookup(self._level_data, "LevelLitres"))

    @property
    def serial_number(self) -> str:
        """Return the serial number of the tank."""
        self._cache_tank_data()
        return (
            self._tank_info["Signalman No"]
            if "Signalman No" in self._tank_info
            else self._tank_info["Serial No"]
        )

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
    def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        self._cache_tank_data()
        return datetime.fromisoformat(
            self.property_lookup(self._level_data, "ReadingDate")
        )

    @property
    def history(self) -> APIResponse:
        """Return the history of the tank readings as a list of dicts."""
        history_data = self._client._get_history(self._signalman_no)  # noqa: SLF001
        return self.transform_history_data(history_data)

    def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            data = self._client._get_latest_level(self._signalman_no)  # noqa: SLF001
            self.unpack_tank_data(data)


class AsyncTank(_BaseTank):
    """Asynchronous Tank class."""

    @async_property
    async def level(self) -> int:
        """Return the oil level in the tank in litres."""
        await self._cache_tank_data()
        return int(self.property_lookup(self._level_data, "LevelLitres"))

    @async_property
    async def serial_number(self) -> str:
        """Return the serial number of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Signalman No"]

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
    async def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        await self._cache_tank_data()
        return datetime.fromisoformat(
            self.property_lookup(self._level_data, "ReadingDate")
        )

    @async_property
    async def history(self) -> APIResponse:
        """Return the history of the tank readings as a list of dicts."""
        history_data = await self._client._get_history(  # noqa: SLF001
            self._signalman_no,
        )
        return self.transform_history_data(history_data)

    async def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            response = await self._client._get_latest_level(  # noqa: SLF001
                self._signalman_no,
            )
            self.unpack_tank_data(response)
