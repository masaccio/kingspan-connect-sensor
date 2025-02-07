from datetime import datetime

import pandas as pd

from mock_data import USERNAME, PASSWORD
from connectsensor import SensorClient


def test_status(mock_sync_httpx_post):
    client = SensorClient()
    client.login(USERNAME, PASSWORD)
    tanks = client.tanks
    assert tanks[0].level == 1000
    assert tanks[0].serial_number == "20001000"
    assert tanks[0].model == "TestModel"
    assert tanks[0].name == "TestTank"
    assert tanks[0].capacity == 2000
    tank_history = pd.DataFrame(tanks[0].history)
    reading_date = tank_history.reading_date[0].to_pydatetime()
    assert reading_date == datetime(2021, 1, 25, 13, 59, 14)
    assert tank_history.level_percent[1] == 95
    assert tank_history.level_litres[2] == 1880
