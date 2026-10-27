"""Tank class for Connect Sensor API."""

from datetime import datetime
from typing import Any, cast

from connectsensor.const import APIResponseValue


class _BaseTank:
    """Base class for Tanks."""

    def __init__(self, client: Any, signalman_no: str) -> None:  # noqa: ANN401
        """Initialize a Tank instance."""
        self._client = client
        self._signalman_no = signalman_no
        self._level_data: dict[str, Any] = {}
        self._tank_info: dict[str, Any] = {}

    def clear_cache(self) -> None:
        """Clear the cached tank data to force a network refresh on next access."""
        self._level_data = {}
        self._tank_info = {}

    def unpack_tank_data(self, response: dict[str, Any]) -> None:
        """Extract level and tank information from the API response."""
        self._level_data = cast("dict[str, Any]", response["level"])
        tank_info_list = cast("list[dict[str, Any]]", response["tankInfo"])
        self._tank_info = {str(x["name"]): x["value"] for x in tank_info_list}

    def format_reading_date(self, date: datetime | str) -> datetime:
        """Format the reading date string into a datetime object."""
        if isinstance(date, datetime):
            return date
        return datetime.fromisoformat(str(date))

    def transform_history_data(
        self,
        data: list[dict[str, Any]],
    ) -> list[dict[str, APIResponseValue]]:
        """Transform raw tank history data into a list of dicts."""
        return [
            {
                "reading_date": self.format_reading_date(cast("str", x["readingDate"])),
                "level_percent": cast("APIResponseValue", x["levelPercentage"]),
                "level_litres": cast("APIResponseValue", x["levelLitres"]),
            }
            for x in data
        ]


class Tank(_BaseTank):
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
        return str(
            self._tank_info.get(
                "Signalman No",
                self._tank_info.get("Serial No", "Unknown"),
            ),
        )

    @property
    def model(self) -> str:
        """Return the model of the tank."""
        self._cache_tank_data()
        return str(self._tank_info.get("Model", "Unknown"))

    @property
    def name(self) -> str:
        """Return the name of the tank."""
        self._cache_tank_data()
        return str(self._tank_info.get("Tank Name", "Unknown"))

    @property
    def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        self._cache_tank_data()
        return int(self._tank_info.get("Tank Capacity(L)", 0))

    @property
    def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        self._cache_tank_data()
        return self.format_reading_date(cast("str", self._level_data["readingDate"]))

    def history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, APIResponseValue]]:
        """Return the history of the tank readings as a list of dicts."""
        history_data = self._client._get_history(  # noqa: SLF001 # pylint: disable=protected-access
            self._signalman_no,
            start_date,
            end_date,
        )
        return self.transform_history_data(cast("list[dict[str, Any]]", history_data))

    def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if not self._level_data:
            data = self._client._get_latest_level(self._signalman_no)  # noqa: SLF001 # pylint: disable=protected-access
            self.unpack_tank_data(cast("dict[str, Any]", data))


class AsyncTank(_BaseTank):
    """Asynchronous Tank class."""

    @property
    async def level(self) -> int:
        """Return the oil level in the tank in litres."""
        await self._cache_tank_data()
        return int(self._level_data["levelLitres"])

    @property
    async def serial_number(self) -> str:
        """Return the serial number of the tank."""
        await self._cache_tank_data()
        return str(
            self._tank_info.get(
                "Signalman No",
                self._tank_info.get("Serial No", "Unknown"),
            ),
        )

    @property
    async def model(self) -> str:
        """Return the model of the tank."""
        await self._cache_tank_data()
        return str(self._tank_info.get("Model", "Unknown"))

    @property
    async def name(self) -> str:
        """Return the name of the tank."""
        await self._cache_tank_data()
        return str(self._tank_info.get("Tank Name", "Unknown"))

    @property
    async def capacity(self) -> int:
        """Return the capacity of the tank in litres."""
        await self._cache_tank_data()
        return int(self._tank_info.get("Tank Capacity(L)", 0))

    @property
    async def last_read(self) -> datetime:
        """Return the last read date of the tank as a datetime object."""
        await self._cache_tank_data()
        return self.format_reading_date(cast("str", self._level_data["readingDate"]))

    async def history(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[dict[str, APIResponseValue]]:
        """Return the history of the tank readings as a list of dicts."""
        history_data = await self._client._get_history(  # noqa: SLF001 # pylint: disable=protected-access
            self._signalman_no,
            start_date,
            end_date,
        )
        return self.transform_history_data(cast("list[dict[str, Any]]", history_data))

    async def _cache_tank_data(self) -> None:
        """Cache the latest tank data if not already cached."""
        if not self._level_data:
            response = await self._client._get_latest_level(  # noqa: SLF001 # pylint: disable=protected-access
                self._signalman_no,
            )
            self.unpack_tank_data(cast("dict[str, Any]", response))
