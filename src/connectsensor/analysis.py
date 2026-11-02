"""Analytics and forecasting utilities for tank data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TypedDict


class TankHistoryPoint(TypedDict):
    """Single point of tank history returned by the Kingspan API."""

    level_litres: float
    reading_date: datetime


@dataclass(slots=True)
class TankData:  # pylint: disable=too-many-instance-attributes
    """Structured aggregate tank data and forecasts."""

    level: float = 0.0
    serial_number: str = ""
    model: str = ""
    name: str = ""
    capacity: float = 0.0
    last_read: datetime | None = None
    history: list[TankHistoryPoint] = field(default_factory=list)
    usage_rate: float = 0.0
    forecast_empty: int = 0


def filter_history(
    history: list[TankHistoryPoint] | None, usage_window: int
) -> list[TankHistoryPoint]:
    """Filter tank history to a smaller recent window of days, sorted chronologically."""
    if not history:
        return []

    # Always generate a naive current time
    cutoff = datetime.now() - timedelta(days=usage_window)  # noqa: DTZ005

    filtered_history: list[TankHistoryPoint] = []
    for point in history:
        dt_naive = point["reading_date"].replace(tzinfo=None)
        filtered_history.append(
            {
                "level_litres": point["level_litres"],
                "reading_date": dt_naive,
            }
        )

    recent = [point for point in filtered_history if point["reading_date"] >= cutoff]
    recent.sort(key=lambda x: x["reading_date"])
    return recent


def calculate_usage_rate(history: list[TankHistoryPoint], refill_threshold: float = 1.1) -> float:
    """Calculate the average daily usage rate over the filtered window."""
    if len(history) < 2: # noqa: PLR2004
        return 0.0

    total_drop = 0.0
    total_days = 0.0

    prev_level = history[0]["level_litres"]
    prev_date = history[0]["reading_date"]

    for row in history[1:]:
        curr_level = row["level_litres"]
        curr_date = row["reading_date"]

        if prev_level != 0 and (curr_level / prev_level) < refill_threshold:
            drop = prev_level - curr_level
            # Calculate elapsed time in days
            days = (curr_date - prev_date).total_seconds() / 86400.0

            if days > 0 and drop >= 0:
                total_drop += drop
                total_days += days

        prev_level = curr_level
        prev_date = curr_date

    if total_days <= 0:
        return 0.0

    return total_drop / total_days


def calculate_forecast_empty(history: list[TankHistoryPoint], rate: float) -> int:
    """Estimate how many days until the tank is empty."""
    if not history or rate == 0:
        return 0

    current_level = int(history[-1]["level_litres"])
    return int(current_level / abs(rate))
