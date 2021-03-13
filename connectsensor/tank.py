from zeep.helpers import serialize_object
import pandas as pd
import sqlite3
import ssl
import sys


class DBError(Exception):
    pass


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
        df = df[["ReadingDate", "LevelPercentage", "LevelLitres"]]
        df.columns = ["reading_date", "level_percent", "level_litres"]
        return df

    def cached_history(self, cache_db, update=False):
        try:
            conn = sqlite3.connect(cache_db)
            cur = conn.cursor()
        except Error as e:
            raise DBError(f"{cache_db}: connection failed") from e

        if _table_exists(cur):
            query = "SELECT * FROM history;"
            old_history = pd.read_sql_query(query, conn, parse_dates=["reading_date"])
            new_history = self.history()
            history = old_history.append(new_history).drop_duplicates()

        if update:
            history.to_sql("history", conn, if_exists="replace", index=False)

        cur.close()
        conn.close()

        return history


def _table_exists(cur):
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
    try:
        cur.execute(query)
        rows = cur.fetchall()
    except Error as e:
        raise DBError("Failed to check status of history table") from e
    return len(rows) > 0
