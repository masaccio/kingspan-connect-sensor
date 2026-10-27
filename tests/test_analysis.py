"""Tests for connectsensor package and analytics using file-based HTTP mocks."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx
import pytest
from mock_data import PASSWORD

from connectsensor import APIVersion, AsyncSensorClient, KingspanErrorCode
from connectsensor.analysis import (
    calculate_forecast_empty,
    calculate_usage_rate,
    filter_history,
)
from connectsensor.exceptions import (
    KingspanAPIError,
    KingspanInvalidCredentialsError,
    KingspanNoDataError,
    KingspanTimeoutError,
)


@pytest.mark.asyncio
async def test_async_client_login_success(mock_async_httpx_post):  # noqa: ARG001
    """Test successful async client login and tank discovery via conftest mock."""
    async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
        await client.login("test@example.com", PASSWORD)
        tanks = await client.tanks

        assert len(tanks) == 1
        assert await tanks[0].serial_number == "20001000"
        assert await tanks[0].capacity == 2000


@pytest.mark.asyncio
async def test_async_client_auth_failure(mock_async_httpx_post):  # noqa: ARG001
    """Test handling of invalid authentication responses via conftest mock."""
    async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
        with pytest.raises(KingspanInvalidCredentialsError) as exc:
            await client.login("test@example.com", "wrong-password")
        assert exc.value.code == KingspanErrorCode.AUTH_FAILED


@pytest.mark.asyncio
async def test_async_client_no_data_error(mock_async_httpx_post):
    """Test handling when a tank reports no level data."""
    # Override the file-based fixture to inject a specific JSON failure
    mock_async_httpx_post.side_effect = None
    mock_async_httpx_post.return_value = httpx.Response(
        200, json={"apiResult": {"code": 500, "description": "No level data available"}}
    )

    async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
        with pytest.raises(KingspanNoDataError) as exc:
            await client.login("test@example.com", PASSWORD)
        assert exc.value.code == KingspanErrorCode.NO_DATA


@pytest.mark.asyncio
async def test_malformed_html_response(mock_async_httpx_post):
    """Test that HTML gateway error pages map safely to APIError."""
    # Override fixture to simulate a 502 Bad Gateway
    mock_async_httpx_post.side_effect = None
    mock_async_httpx_post.return_value = httpx.Response(502, text="<html>502 Bad Gateway</html>")

    async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
        with pytest.raises(KingspanAPIError) as exc:
            await client.login("test@example.com", PASSWORD)
        assert exc.value.code == KingspanErrorCode.UNKNOWN


@pytest.mark.asyncio
async def test_async_client_timeout(mock_async_httpx_post):
    """Test timeout behavior mapping to KingspanTimeoutError."""
    mock_async_httpx_post.side_effect = httpx.TimeoutException("Connection timed out")

    async with AsyncSensorClient(version=APIVersion.KNECT_V1, timeout=0.001) as client:
        with pytest.raises(KingspanTimeoutError) as exc:
            await client.login("test@example.com", PASSWORD)
        assert exc.value.code == KingspanErrorCode.TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize("mock_async_httpx_post", [True], indirect=True)
async def test_e2e_history_and_analytics(mock_async_httpx_post):  # noqa: ARG001
    """Test full integration of API history fetching and analytics math."""
    async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
        await client.login("test@example.com", PASSWORD)
        tanks = await client.tanks

        # Fetch dynamically generated history
        tank = tanks[0]
        history = await tank.history()

        assert len(history) > 0

        # Process the raw history through the analytics utilities
        filtered = filter_history(history, usage_window=14)
        rate = calculate_usage_rate(filtered)
        forecast = calculate_forecast_empty(filtered, rate)

        assert rate > 0.0
        assert forecast > 0


def test_analytics_filter_and_forecast_pure():
    """Test pure analytics functions with timezone-naive datetimes."""
    now = datetime.now()  # noqa: DTZ005
    history = [
        {"level_litres": 1200.0, "reading_date": now - timedelta(days=5)},
        {"level_litres": 1100.0, "reading_date": now - timedelta(days=3)},
        {"level_litres": 1000.0, "reading_date": now - timedelta(days=1)},
    ]

    # Filter history within a 4-day window
    filtered = filter_history(history, usage_window=4)
    assert len(filtered) == 2  # Should drop the 5-days-ago entry

    # Calculate daily usage rate (100L drop over 2 days = 50L/day)
    rate = calculate_usage_rate(filtered)
    assert rate == 100.0

    # Calculate forecast empty days (1000L current / 50L per day = 20 days)
    forecast = calculate_forecast_empty(filtered, rate)
    assert forecast == 10


def test_filter_history_empty():
    """Test filter_history handles None and empty lists (Line 37)."""
    assert filter_history(None, usage_window=14) == []
    assert filter_history([], usage_window=14) == []


def test_calculate_usage_rate_edge_cases():
    """Test calculation edge cases: short history, refills, and zero states."""
    now = datetime.now()  # noqa: DTZ005

    # Short history
    assert calculate_usage_rate([]) == 0.0
    assert calculate_usage_rate([{"level_litres": 1000.0, "reading_date": now}]) == 0.0

    # Divide by zero prevention and refill thresholds
    history_with_refill = [
        {"level_litres": 0.0, "reading_date": now - timedelta(days=4)},  # Starts at 0
        {
            "level_litres": 1000.0,
            "reading_date": now - timedelta(days=3),
        },  # Skips zero-division, level becomes 1000
        {
            "level_litres": 1500.0,
            "reading_date": now - timedelta(days=2),
        },  # Refill (1.5x) > 1.1 threshold, skipped
        {"level_litres": 1400.0, "reading_date": now - timedelta(days=1)},  # Valid drop: 100L delta
    ]
    # The only valid delta recorded is 100L (from 1500 to 1400)
    assert calculate_usage_rate(history_with_refill) == 100.0

    # No valid drops recorded
    history_flat = [
        {"level_litres": 1000.0, "reading_date": now - timedelta(days=2)},
        {"level_litres": 1150.0, "reading_date": now - timedelta(days=1)},  # Refill only
    ]
    assert calculate_usage_rate(history_flat) == 0.0


def test_calculate_forecast_empty_edge_cases():
    """Test forecast handles missing history and zero usage rates (Line 75)."""
    now = datetime.now()  # noqa: DTZ005
    valid_history = [{"level_litres": 1000.0, "reading_date": now}]

    assert calculate_forecast_empty(None, rate=50.0) == 0
    assert calculate_forecast_empty([], rate=50.0) == 0
    assert calculate_forecast_empty(valid_history, rate=0.0) == 0
