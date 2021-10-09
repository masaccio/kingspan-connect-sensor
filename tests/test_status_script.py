from pytest import mark
from unittest.mock import patch

from mock_requests import mock_get, mock_post
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


VALID_STATUS = [
    "TestTank:",
    "Capacity = 2000",
    "Serial Number = 20001000",
    "Model = TestModel",
    "Level = 50% (1000 litres)",
    "Last Read = 2021-01-31 00:59:30.987000",
    "",
    "History:",
    "Reading date           %Full  Litres",
    "25-Jan-2021 13:59      100    2000",
    "27-Jan-2021 00:59      95     1900",
    "29-Jan-2021 00:59      94     1880",
    "30-Jan-2021 00:29      94     1880",
    "31-Jan-2021 00:59      92     1840",
    "",
]


@mark.script_launch_mode("inprocess")
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
