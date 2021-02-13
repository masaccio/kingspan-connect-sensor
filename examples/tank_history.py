import argparse
import netrc
import sqlite3
import sys
import pandas as pd

from connectsensor import SensorClient
from pathlib import Path
from datetime import datetime


DEFAULT_DB_PATH = Path.home() / ".kingspan/history.db"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--db",
    default=DEFAULT_DB_PATH,
    help="DB path (default: " + str(DEFAULT_DB_PATH) + ")",
)
parser.add_argument(
    "--start-date",
    required=False,
    type=lambda d: datetime.strptime(d, "%Y-%m-%d"),
    help="Start date YYYY-MM-DD",
)

args = parser.parse_args()

netrc = netrc.netrc()
auth = netrc.authenticators("www.connectsensor.com")
client = SensorClient()
client.login(auth[0], auth[2])

tanks = client.tanks()
history = tanks[0].history()

try:
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
except OSError as e:
    print(args.db + ": " + str(e))

try:
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()
except Error as e:
    print("DB error:", str(e))
else:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='history'")
    rows = cur.fetchall()
    if len(rows) > 0:
        old_history = pd.read_sql_query(
            "select * from history;", conn, parse_dates=["reading_date"]
        )
        history = old_history.append(history).drop_duplicates()

    if args.start_date:
        history = history[history["reading_date"] > args.start_date]
    history.to_sql("history", conn, if_exists="replace", index=False)
    print(history.sort_values(by=["reading_date"]))
finally:
    cur.close()
    conn.close()
