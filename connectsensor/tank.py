from zeep.helpers import serialize_object
import pandas as pd


class Tank:
    def __init__(self, client, tank_info):
        self._client = client
        self._tank_info = tank_info

    def level(self):
        response = self._client.get_latest_level(self._tank_info["SignalmanNo"])
        self._tank_info_items = response["TankInfo"]["APITankInfoItem"]
        level_data = response["Level"]
        return dict(serialize_object(level_data))

    def _lookup_tank_info_item(self, item_name):
        if not hasattr(self, "_tank_info_items"):
            self.level()

        for item in self._tank_info_items:
            if item["Name"] == item_name:
                return item["Value"]
        return None

    def serial_number(self):
        return self._lookup_tank_info_item("Serial No")

    def model(self):
        return self._lookup_tank_info_item("Model")

    def name(self):
        return self._lookup_tank_info_item("Tank Name")

    def capacity(self):
        return self._lookup_tank_info_item("Tank Capacity(L)")

    def history(self):
        history_data = self._client.get_history(self._tank_info["SignalmanNo"])
        df = pd.DataFrame(serialize_object(history_data))
        df =  df[["ReadingDate", "LevelPercentage", "LevelLitres"]]
        df.columns = ["reading_date", "level_percent", "level_litres"]
        return df
