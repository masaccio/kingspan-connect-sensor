import argparse
import configparser
import pandas as pd
import sqlite3
import sys

from connectsensor import SensorClient, APIError, DBError
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


def table_exists(cursor):
    query = "SELECT name FROM sqlite_master WHERE type='table' AND name='history'"
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
    except sqlite3.Error as e:
        raise DBError("Failed to check status of history table") from e
    return len(rows) > 0


def cached_history(tank, cache_db, update):
    history = pd.DataFrame()
    try:
        db = sqlite3.connect(cache_db)
        cursor = db.cursor()
    except sqlite3.Error as e:
        raise DBError(f"{cache_db}: connection failed") from e

    if table_exists(cursor):
        query = "SELECT * FROM history;"
        old_history = pd.read_sql_query(query, db, parse_dates=["reading_date"])
        new_history = tank.history
        history = pd.concat([old_history, new_history]).drop_duplicates()
    else:
        history = tank.history

    if update:
        history.to_sql("history", db, if_exists="replace", index=False)

    cursor.close()
    db.close()

    return history


def read_tank_history(config, update):
    try:
        client = SensorClient()
        client.login(
            config_value(config, "sensit", "username"),
            config_value(config, "sensit", "password"),
        )
    except APIError as e:
        if "Authentication Failed" in str(e):
            print(
                "Authentication Failed: invalid username or password", file=sys.stderr
            )
        else:  # pragma: no cover
            print("Unknown API error:", e.value, file=sys.stderr)
        sys.exit(1)

    cache_db = config_value(config, "sensit", "cache")
    tanks = client.tanks
    try:
        tank_history = cached_history(tanks[0], cache_db, update)
    except DBError as e:
        print("DB update failed:", str(e))
        sys.exit(1)
    return tank_history


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
    "-U",
    "--update",
    action="store_true",
    default=False,
    help="Update cache with new data (deault: false)",
)


def main():
    args = parser.parse_args()
    config = read_config(args.config)

    tank_history = read_tank_history(config, args.update)
    start_date = config.get("sensit", "start-date", fallback=None)
    if start_date is not None:
        tank_history = tank_history[tank_history.reading_date >= start_date]

    writer = pd.ExcelWriter(args.output, engine="xlsxwriter")
    tank_history.to_excel(writer, sheet_name="History", index=False)
    writer.close()


if __name__ == "__main__":
    # execute only if run as a script
    main()
