from datetime import datetime

import pandas as pd
import pytest

from mock_data import PASSWORD, USERNAME

from connectsensor import AsyncSensorClient


@pytest.mark.asyncio
async def test_status(async_mock_zeep):
    async with AsyncSensorClient() as client:
        await client.login(USERNAME, PASSWORD)
        tanks = await client.tanks
        assert await tanks[0].level == 1000
        assert await tanks[0].serial_number == "20001000"
        assert await tanks[0].model == "TestModel"
        assert await tanks[0].name == "TestTank"
        assert await tanks[0].capacity == 2000

        tank_history = await tanks[0].history
        tank_history = pd.DataFrame(tank_history)
        assert tank_history.reading_date[0] == datetime(2021, 1, 25, 13, 59, 14)
        assert tank_history.level_percent[1] == 95
        assert tank_history.level_litres[2] == 1880
