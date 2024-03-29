import pandas as pd
import sqlite3

from datetime import datetime
from pathlib import Path
from pytest import mark
from unittest.mock import patch

from mock_requests import mock_get, mock_requests_post, mock_requests_post_generate
from mock_data import VALID_STATUS, USERNAME, PASSWORD, VALID_DATA, NEW_TEST_DATA
from connectsensor import __version__


@mark.script_launch_mode("subprocess")
def test_help(script_runner):
    ret = script_runner.run("kingspan-notifier", print_result=False)
    assert "usage: kingspan-notifier [-h]" in ret.stderr
    assert ret.stdout == ""
    assert ret.success == False


@mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner):
    ret = script_runner.run("kingspan-notifier", "--help", print_result=False)
    assert "usage: kingspan-notifier [-h]" in ret.stdout
    assert "config CONFIG" in ret.stdout
    assert ret.stderr == ""
    assert ret.success


@patch("requests.sessions.Session.post", side_effect=mock_requests_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_help_invalid_credentials(mock_get, mock_post, script_runner):
    ret = script_runner.run(
        "kingspan-notifier",
        "--config=tests/data/invalid_config.ini",
        print_result=False,
    )

    assert "invalid username or password" in ret.stderr
    assert ret.stdout == ""
    assert not ret.success


@mark.script_launch_mode("inprocess")
@patch("requests.sessions.Session.post", side_effect=mock_requests_post_generate)
@patch("requests.sessions.Session.get", side_effect=mock_get)
@patch("smtplib.SMTP_SSL")
def test_notify_empty(mock_smtp, mock_get, mock_post, script_runner):
    Path("test.db").unlink(missing_ok=True)
    ret = script_runner.run(
        "kingspan-notifier",
        "--config=tests/data/config.ini",
        print_result=False,
    )
    assert ret.stderr == ""
    assert "Current level 200 litres" in ret.stdout
    assert "empty in 1 days" in ret.stdout
    assert ret.success
    assert mock_smtp().__enter__().login.call_count == 1
    assert mock_smtp.mock_calls[0].args == ("smtp.example.com", 465)
