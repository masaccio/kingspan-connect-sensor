import argparse
import configparser
import os
import pandas as pd
import sqlite3
import sys
import xlsxwriter

from connectsensor import SensorClient, APIError
from datetime import datetime, timedelta


def read_config(config_filename):
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_filename)
    except configparser.Error as e:
        print(config_filename + ": " + str(e))
        sys.exit(1)
    finally:
        return config


def config_value(config, section, key):
    try:
        value = config.get(section, key)
    except configparser.Error as e:
        print(f"Config value '{key}' not found in section '{section}'", file=sys.stderr)
        sys.exit(1)
    finally:
        return value


def read_tank_history(config):
    try:
        client = SensorClient()
        client.login(
            config_value(config, "sensit", "username"),
            config_value(config, "sensit", "password"),
        )
    except APIError as e:
        print("SENSiT connect failed:", str(e))
        sys.exit(1)
    else:
        cache_db = config_value(config, "sensit", "cache")
        tanks = client.tanks()
        tank_history = tanks[0].cached_history(cache_db, update=True)
        return tank_history

    @property
    def history(self):
        history_data = self._soap_client._get_history(self._signalman_no)
        return history_to_df(history_data)


def cached_history(self, cache_db, update=False):
    try:
        db = sqlite3.connect(cache_db)
        cursor = conn.cursor()
    except sqlite3.Error as e:
        raise DBError(f"{cache_db}: connection failed") from e

    if table_exists(cursor):
        query = "SELECT * FROM history;"
        old_history = pd.read_sql_query(query, db, parse_dates=["reading_date"])
        new_history = self.history()
        history = old_history.concat(new_history).drop_duplicates()

    if update:
        history.to_sql("history", db, if_exists="replace", index=False)

    cursor.close()
    db.close()

    return history


def table_exists(cur):
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
    try:
        cur.execute(query)
        rows = cur.fetchall()
    except sqlite3.Error as e:
        raise DBError("Failed to check status of history table") from e
    return len(rows) > 0


parser = argparse.ArgumentParser()
parser.add_argument(
    "-o",
    "--output",
    required=False,
    default="history.xlsx",
    help="Excel output file for history, default=history.xlsx",
)
parser.add_argument(
    "-c",
    "--config",
    required=True,
    help="Config file in ini-format",
)
parser.add_argument(
    "-N",
    "--no-update",
    action="store_true",
    default=False,
    help="Don't update cache with new data (deault: update on)",
)


def main():
    args = parser.parse_args()
    config = read_config(args.config)

    tank_history = read_tank_history(config)
    start_date = config.get("sensit", "start-date", fallback=None)
    if start_date is not None:
        tank_history = tank_history[tank_history.reading_date >= start_date]

    writer = pd.ExcelWriter(args.output, engine="xlsxwriter")
    tank_history.to_excel(writer, sheet_name="History", index=False)
    writer.save()


if __name__ == "__main__":
    # execute only if run as a script
    main()
