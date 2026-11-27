"""Payload data models for interacting with the Kingspan Connect Sensor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from connectsensor.exceptions import KingspanInvalidResponseError

if TYPE_CHECKING:
    from connectsensor.analysis import TankHistoryPoint


def _parse_datetime(value: object, field_name: str) -> datetime:
    """Ensure that datetimes from the API parse cleanly or raise an exception."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            msg = f"Invalid ISO datetime for '{field_name}': {value!r}"
            raise KingspanInvalidResponseError(
                msg,
            ) from exc
    msg = f"Expected datetime or str for '{field_name}', got {type(value).__name__}"
    raise KingspanInvalidResponseError(msg)


@dataclass(frozen=True, slots=True)
class LoginPayload:
    """Dataclass model for login response from API."""

    user_id: str
    signalman_numbers: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoginPayload:
        """Transform a JSON payload or raise an exception if malformed."""
        try:
            user_id = str(data["apiUserID"])
            raw_tanks = data["tanks"]
            if not isinstance(raw_tanks, list):
                msg = f"Expected list for 'tanks', got {type(raw_tanks).__name__}"
                raise TypeError(msg)  # noqa: TRY301
            signalman_numbers = [str(tank["signalmanNo"]) for tank in raw_tanks]
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"Malformed login response: {exc}"
            raise KingspanInvalidResponseError(msg) from exc
        return cls(user_id=user_id, signalman_numbers=signalman_numbers)


@dataclass(frozen=True, slots=True)
class LatestLevelPayload:
    """Dataclass model for level response from API."""

    level_litres: int
    reading_date: datetime
    model: str
    name: str
    capacity: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LatestLevelPayload:
        """Transform a JSON payload or raise an exception if malformed."""
        try:
            level = data["level"]
            tank_info_raw = data["tankInfo"]
            if not isinstance(level, dict) or not isinstance(tank_info_raw, list):
                msg = "Unexpected structure for 'level' or 'tankInfo'"
                raise TypeError(msg)  # noqa: TRY301

            tank_info = {str(item["name"]): item["value"] for item in tank_info_raw}
            return cls(
                level_litres=int(float(level["levelLitres"])),
                reading_date=_parse_datetime(level["readingDate"], "readingDate"),
                model=str(tank_info.get("Model", "Unknown")),
                name=str(tank_info.get("Tank Name", "Unknown")),
                capacity=int(float(tank_info.get("Tank Capacity(L)", 0))),
            )
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"Malformed latest level response: {exc}"
            raise KingspanInvalidResponseError(msg) from exc


@dataclass(frozen=True, slots=True)
class HistoryPayload:
    """Dataclass model for history response from API."""

    points: list[TankHistoryPoint]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HistoryPayload:
        """Transform a JSON payload or raise an exception if malformed."""
        try:
            raw_levels = data["levels"]
            if raw_levels is None:
                return cls(points=[])
            if not isinstance(raw_levels, list):
                msg = f"Expected list for 'levels', got {type(raw_levels).__name__}"
                raise TypeError(msg)  # noqa: TRY301

            points: list[TankHistoryPoint] = []
            for item in raw_levels:
                if not isinstance(item, dict):
                    msg = f"Expected dict for history entry, got {type(item).__name__}"
                    raise TypeError(msg)  # noqa: TRY301
                point: TankHistoryPoint = {
                    "reading_date": _parse_datetime(item["readingDate"], "readingDate"),
                    "level_litres": float(item["levelLitres"]),
                }
                if item.get("levelPercentage") is not None:
                    point["level_percent"] = float(item["levelPercentage"])
                points.append(point)
        except (KeyError, TypeError, ValueError) as exc:
            msg = f"Malformed history response: {exc}"
            raise KingspanInvalidResponseError(msg) from exc
        return cls(points=points)
