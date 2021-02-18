import argparse
import configparser
import numpy as np
import os
import pandas as pd
import smtplib
import sqlite3
import ssl
import sys

cwd = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, cwd + "/../")

from connectsensor import SensorClient
from datetime import datetime, timedelta


def time_delta_days(td):
    return td.days + (td.seconds / 3600) / 24


def send_email(server, username, password, email, subject, message):
    port = 465
    message = (
        f"From: SENSiT Notifier <{email}>\n"
        f"To: <{email}>\n"
        f"Subject: {subject}\n\n" + message
    )
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(server, port, context=context) as server:
        server.login(username, password)
        server.sendmail(email, email, message)


def read_config(config_filename):
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read(config_filename)
    except Error as e:
        print(config_filename + ": " + str(e))
        sys.exit(1)
    finally:
        return config


def config_value(config, section, key):
    try:
        value = config.get(section, key)
    except Error as e:
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
    finally:
        tanks = client.tanks()
        return tanks[0].history()


def update_tank_cache(config, history, update=False):
    cache_db = config.get("sensit", "cache", fallback=None)
    if cache_db is None:
        return

    start_date = config.get("sensit", "start-date", fallback=None)
    if start_date is not None:
        history = history[history.reading_date >= start_date]

    try:
        conn = sqlite3.connect(cache_db)
        cur = conn.cursor()
    except Error as e:
        print("DB error:", str(e))
        sys.exit(1)

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
    rows = cur.fetchall()
    if len(rows) > 0:
        old_history = pd.read_sql_query(
            "select * from history;", conn, parse_dates=["reading_date"]
        )
        history = old_history.append(history).drop_duplicates()

    if update:
        history.to_sql("history", conn, if_exists="replace", index=False)

    cur.close()
    conn.close()

    return history


# Ignore refill days where oil goes up by 'threshold'
def remove_refills(history, threshold):
    current_level = history.level_litres.iloc[0]
    new_levels = [current_level]
    for index, row in history.iloc[1:].iterrows():
        if (row.level_litres / current_level) > threshold:
            new_levels.append(current_level)
        else:
            new_levels.append(row.level_litres)
    return new_levels


def forecast_empty(config, history, window):
    time_delta = datetime.today() - timedelta(days=window)
    history = history[history.reading_date >= time_delta]

    threshold = config.get("sensit", "refill-threshold", fallback=1.25)
    levels = remove_refills(history, threshold)
    delta_days = history.reading_date - history.reading_date.min()
    delta_days = delta_days.astype("timedelta64[h]") / 24

    rate = np.polyfit(delta_days, levels, 1)[0]
    current_level = int(history.level_litres.tail(1))
    return int(current_level / abs(rate))


parser = argparse.ArgumentParser()
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
parser.add_argument(
    "-w",
    "--window",
    default=14,
    type=int,
    help="Number of days history to consider (default: 14)",
)
parser.add_argument(
    "-n",
    "--notice",
    default=14,
    type=int,
    help="Number of days before out-of-oil forecast to warn (default: 14)",
)

args = parser.parse_args()
config = read_config(args.config)

tank_history = read_tank_history(config)
tank_history = update_tank_cache(config, tank_history, args.no_update)
days_to_empty = forecast_empty(config, tank_history, args.window)

if days_to_empty < args.notice:
    level_percent = tank_history.level_percent.iloc[-1]
    level_litres = tank_history.level_litres.iloc[-1]

    message = "SENSiT is reporting:\n"
    message += f"    * level at {level_percent}%\n"
    message += f"    * level at {level_litres} litres\n\n"
    message += f"Forecasting empty in {days_to_empty} days\n"

    send_email(
        config_value(config, "smtp", "server"),
        config_value(config, "smtp", "username"),
        config_value(config, "smtp", "password"),
        config_value(config, "smtp", "email"),
        "Low oil warning from SENSiT",
        message,
    )

    print(f"Sent notification: empty in {days_to_empty} days")
else:
    print(f"No notification; {days_to_empty} days oil remain")
