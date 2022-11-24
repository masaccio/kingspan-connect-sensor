from async_property import async_property
from zeep.helpers import serialize_object

import pandas as pd
import sqlite3

from .exceptions import DBError


class Tank:
    def __init__(self, soap_client: object, signalman_no: str):
        self._soap_client = soap_client
        self._signalman_no = signalman_no
        self._level_data = None

    @property
    def level(self) -> int:
        """Return the oil level in the tank in litres"""
        self._cache_tank_data()
        return self._level_data["Level"]

    @property
    def serial_number(self) -> str:
        self._cache_tank_data()
        return self._tank_info["Serial No"]

    @property
    def model(self) -> str:
        self._cache_tank_data()
        return self._tank_info["Model"]

    @property
    def name(self) -> str:
        self._cache_tank_data()
        return self._tank_info["Tank Name"]

    @property
    def capacity(self):
        """Return the capacity of the tank in litres"""
        self._cache_tank_data()
        return self._tank_info["Tank Capacity(L)"]

    @property
    def history(self):
        history_data = self._soap_client._get_history(self._signalman_no)
        return history_to_df(history_data)

    def cached_history(self, cache_db, update=False):
        try:
            conn = sqlite3.connect(cache_db)
            cur = conn.cursor()
        except sqlite3.Error as e:
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

    def _cache_tank_data(self):
        if self._level_data is None:
            response = self._soap_client._get_latest_level(self._signalman_no)
            unpack_tank_data(self, response)


class AsyncTank:
    def __init__(self, soap_client: object, signalman_no: str):
        self._soap_client = soap_client
        self._signalman_no = signalman_no
        self._level_data = None

    @async_property
    async def level(self) -> int:
        await self._cache_tank_data()
        return int(self._level_data["LevelLitres"])

    @async_property
    async def serial_number(self) -> str:
        await self._cache_tank_data()
        return self._tank_info["Serial No"]

    @async_property
    async def model(self) -> str:
        await self._cache_tank_data()
        return self._tank_info["Model"]

    @async_property
    async def name(self) -> str:
        await self._cache_tank_data()
        return self._tank_info["Tank Name"]

    @async_property
    async def capacity(self):
        await self._cache_tank_data()
        return int(self._tank_info["Tank Capacity(L)"])

    @async_property
    async def history(self):
        history_data = await self._soap_client._get_history(self._signalman_no)
        return history_to_df(history_data)

    async def cached_history(self, cache_db, update=False):
        try:
            conn = sqlite3.connect(cache_db)
            cur = conn.cursor()
        except sqlite3.Error as e:
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

    async def _cache_tank_data(self):
        if self._level_data is None:
            response = await self._soap_client._get_latest_level(self._signalman_no)
            unpack_tank_data(self, response)


def unpack_tank_data(cls, response):
    cls._level_data = serialize_object(response["Level"])
    tank_info = serialize_object(response["TankInfo"])
    cls._tank_info = {x["Name"]: x["Value"] for x in tank_info["APITankInfoItem"]}


def history_to_df(history_data):
    df = pd.DataFrame(serialize_object(history_data))
    df = df[["ReadingDate", "LevelPercentage", "LevelLitres"]]
    df.columns = ["reading_date", "level_percent", "level_litres"]
    return df
