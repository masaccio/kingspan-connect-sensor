from pathlib import Path
import pytest
from unittest.mock import patch


@pytest.mark.script_launch_mode("subprocess")
def test_help(script_runner):
    ret = script_runner.run("kingspan-notifier", print_result=False)
    assert "usage: kingspan-notifier [-h]" in ret.stderr
    assert ret.stdout == ""
    assert not ret.success


@pytest.mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner):
    ret = script_runner.run("kingspan-notifier", "--help", print_result=False)
    assert "usage: kingspan-notifier [-h]" in ret.stdout
    assert "config CONFIG" in ret.stdout
    assert ret.stderr == ""
    assert ret.success


@pytest.mark.script_launch_mode("inprocess")
def test_help_invalid_credentials(mock_zeep, script_runner):
    ret = script_runner.run(
        "kingspan-notifier",
        "--config=tests/data/invalid_config.ini",
        print_result=False,
    )

    assert "invalid username or password" in ret.stderr
    assert ret.stdout == ""
    assert not ret.success


@patch("smtplib.SMTP_SSL")
@pytest.mark.script_launch_mode("inprocess")
@pytest.mark.parametrize("mock_zeep", [True], indirect=True)
def test_notify_empty(mock_smtp, mock_zeep, script_runner):
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
