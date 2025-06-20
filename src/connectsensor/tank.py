"""Tank class for Connect Sensor API."""

from async_property import async_property
from zeep.helpers import serialize_object


class Tank:
    def __init__(self, soap_client: object, signalman_no: str) -> None:
        """Initialize a Tank instance."""
        self._soap_client = soap_client
        self._signalman_no = signalman_no
        self._level_data = None

    @property
    def level(self) -> int:
        """Return the oil level in the tank in litres."""
        self._cache_tank_data()
        return int(self._level_data["LevelLitres"])  # type: ignore[reportOptionalSubscript]

    @property
    def serial_number(self) -> str:
        """Return the serial number of the tank."""
        self._cache_tank_data()
        return self._tank_info["Serial No"]  # type: ignore[reportOptionalSubscript]

    @property
    def model(self) -> str:
        """Return the model of the tank."""
        self._cache_tank_data()
        return self._tank_info["Model"]  # type: ignore[reportOptionalSubscript]

    @property
    def name(self) -> str:
        """Return the name of the tank."""
        self._cache_tank_data()
        return self._tank_info["Tank Name"]  # type: ignore[reportOptionalSubscript]

    @property
    def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        self._cache_tank_data()
        return int(self._tank_info["Tank Capacity(L)"])  # type: ignore[reportOptionalSubscript]

    @property
    def last_read(self) -> str:
        """Return the last read date of the tank as a datetime object."""
        self._cache_tank_data()
        return self._level_data["ReadingDate"]  # type: ignore[reportOptionalSubscript]

    @property
    def history(self):
        """Return the history of the tank readings as a list of dicts."""
        history_data = self._soap_client._get_history(self._signalman_no)
        return transform_history_data(history_data)

    def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            response = self._soap_client._get_latest_level(self._signalman_no)
            unpack_tank_data(self, response)


class AsyncTank:
    def __init__(self, soap_client: object, signalman_no: str) -> None:
        """Initialize an AsyncTank instance."""
        self._soap_client = soap_client
        self._signalman_no = signalman_no
        self._level_data = None

    @async_property
    async def level(self) -> int:
        """Return the oil level in the tank in litres."""
        await self._cache_tank_data()
        return int(self._level_data["LevelLitres"])  # type: ignore[reportOptionalSubscript]

    @async_property
    async def serial_number(self) -> str:
        """Return the serial number of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Serial No"]  # type: ignore[reportOptionalSubscript]

    @async_property
    async def model(self) -> str:
        """Return the model of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Model"]  # type: ignore[reportOptionalSubscript]

    @async_property
    async def name(self) -> str:
        """Return the name of the tank."""
        await self._cache_tank_data()
        return self._tank_info["Tank Name"]  # type: ignore[reportOptionalSubscript]

    @async_property
    async def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        await self._cache_tank_data()
        return int(self._tank_info["Tank Capacity(L)"])  # type: ignore[reportOptionalSubscript]

    @async_property
    async def last_read(self) -> str:
        """Return the last read date of the tank as a datetime object."""
        await self._cache_tank_data()
        return self._level_data["ReadingDate"]  # type: ignore[reportOptionalSubscript]

    @async_property
    async def history(self):
        """Return the history of the tank readings as a list of dicts."""
        history_data = await self._soap_client._get_history(self._signalman_no)
        return transform_history_data(history_data)

    async def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if self._level_data is None:
            response = await self._soap_client._get_latest_level(self._signalman_no)
            unpack_tank_data(self, response)


def unpack_tank_data(cls, response) -> None:
    cls._level_data = serialize_object(response["Level"])
    tank_info = serialize_object(response["TankInfo"])
    cls._tank_info = {x["Name"]: x["Value"] for x in tank_info["APITankInfoItem"]}


def transform_history_data(data: dict[str, list[dict]]) -> list[dict]:
    """Transform raw tank history data into a list of dicts."""
    return [
        {
            "reading_date": x["ReadingDate"],
            "level_percent": x["LevelPercentage"],
            "level_litres": x["LevelLitres"],
        }
        for x in data
    ]
