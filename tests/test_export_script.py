import pandas as pd
import sqlite3

from pathlib import Path
from pytest import mark
from unittest.mock import patch

from mock_data import VALID_DATA, NEW_TEST_DATA


@mark.script_launch_mode("subprocess")
def test_help(script_runner):
    ret = script_runner.run("kingspan-export", print_result=False)
    assert "usage: kingspan-export [-h]" in ret.stderr
    assert ret.stdout == ""
    assert not ret.success


@mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner):
    ret = script_runner.run("kingspan-export", "--help", print_result=False)
    assert "usage: kingspan-export [-h]" in ret.stdout
    assert "config CONFIG" in ret.stdout
    assert ret.stderr == ""
    assert ret.success


@mark.script_launch_mode("inprocess")
def test_help_invalid_credentials(mock_zeep, script_runner):
    ret = script_runner.run(
        "kingspan-export",
        "--config=tests/data/invalid_config.ini",
        print_result=False,
    )

    assert "invalid username or password" in ret.stderr
    assert ret.stdout == ""
    assert not ret.success


@mark.script_launch_mode("inprocess")
def test_get_history(mock_zeep, script_runner, tmp_path):
    Path("test.db").unlink(missing_ok=True)
    output_filename = tmp_path / "history.xlsx"
    ret = script_runner.run(
        "kingspan-export",
        "--config=tests/data/config.ini",
        f"--output={output_filename}",
        print_result=False,
    )
    assert ret.stderr == ""
    assert ret.success

    tank_history = pd.read_excel(output_filename)
    tank_history = tank_history.sort_values(by=["reading_date"]).reset_index(drop=True)
    for i, row in enumerate(VALID_DATA):
        assert tank_history.reading_date[i].to_pydatetime() == row[0]
        assert tank_history.level_percent[i] == row[1]
        assert tank_history.level_litres[i] == row[2]


@mark.script_launch_mode("inprocess")
def test_get_cached_history(mock_zeep, script_runner, tmp_path):
    Path("test.db").unlink(missing_ok=True)
    output_filename = tmp_path / "history.xlsx"
    output_filename.unlink(missing_ok=True)
    ret = script_runner.run(
        "kingspan-export",
        "--config=tests/data/config.ini",
        f"--output={output_filename}",
        print_result=False,
    )
    assert ret.stderr == ""
    assert ret.success

    tank_history = pd.read_excel(output_filename)
    tank_history = tank_history.drop(index=[0, 1]).reset_index(drop=True)
    new_data = pd.DataFrame.from_dict(
        {
            "reading_date": [NEW_TEST_DATA[0]],
            "level_percent": [NEW_TEST_DATA[1]],
            "level_litres": [NEW_TEST_DATA[2]],
        },
    )
    tank_history = pd.concat([new_data, tank_history])

    db = sqlite3.connect("test.db")
    tank_history.to_sql("history", db, if_exists="replace", index=False)
    db.close()

    output_filename = tmp_path / "history.xlsx"
    output_filename.unlink(missing_ok=True)
    ret = script_runner.run(
        "kingspan-export",
        "--config=tests/data/config.ini",
        f"--output={output_filename}",
        print_result=False,
    )
    assert ret.stderr == ""
    assert ret.success

    tank_history = pd.read_excel(output_filename)
    tank_history = tank_history.sort_values(by=["reading_date"]).reset_index(drop=True)
    for i, row in enumerate([NEW_TEST_DATA] + VALID_DATA):
        assert tank_history.reading_date[i].to_pydatetime() == row[0]
        assert tank_history.level_percent[i] == row[1]
        assert tank_history.level_litres[i] == row[2]
