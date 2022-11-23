from pytest import mark
from unittest.mock import patch

from mock_requests import mock_get, mock_post
from mock_data import VALID_STATUS, USERNAME, PASSWORD
from connectsensor import __version__


@mark.script_launch_mode("subprocess")
def test_help(script_runner):
    ret = script_runner.run("kingspan-status", print_result=False)
    assert ret.success == False
    assert "usage: kingspan-status [-h]" in ret.stderr
    assert ret.stdout == ""


@mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner):
    ret = script_runner.run("kingspan-status", "--help", print_result=False)
    assert ret.success
    assert "usage: kingspan-status [-h]" in ret.stdout
    assert "username USERNAME" in ret.stdout
    assert ret.stderr == ""


@patch("requests.sessions.Session.post", side_effect=mock_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_help_debug(mock_get, mock_post, script_runner):
    ret = script_runner.run(
        "kingspan-status",
        "--username=test@example.com",
        "--password=s3cret",
        "--debug",
        print_result=False,
    )

    assert ret.success
    assert "Level = 50%" in ret.stdout
    assert "zeep.transports: Loading remote data" in ret.stderr
    assert "HTTP Response from" in ret.stderr
    assert "SoapMobileAPPGetLatestLevel_v3Response" in ret.stderr


@patch("requests.sessions.Session.post", side_effect=mock_post)
@patch("requests.sessions.Session.get", side_effect=mock_get)
def test_status(mock_get, mock_post, script_runner):
    ret = script_runner.run(
        "kingspan-status",
        "--username=test@example.com",
        "--password=s3cret",
        print_result=False,
    )
    assert ret.success
    output = [s.strip() for s in ret.stdout.split("\n")]
    assert output == VALID_STATUS
    assert ret.stderr == ""
