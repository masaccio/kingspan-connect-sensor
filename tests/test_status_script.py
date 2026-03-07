from pytest import mark

from mock_data import VALID_STATUS


@mark.script_launch_mode("subprocess")
def test_help(script_runner):
    ret = script_runner.run("kingspan-status", print_result=False)
    assert not ret.success
    assert "usage: kingspan-status [-h]" in ret.stderr
    assert ret.stdout == ""


@mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner):
    ret = script_runner.run("kingspan-status", "--help", print_result=False)
    assert ret.success
    assert "usage: kingspan-status [-h]" in ret.stdout
    assert "username USERNAME" in ret.stdout
    assert ret.stderr == ""


@mark.script_launch_mode("inprocess")
def test_help_invalid_credentials(script_runner, mock_sync_httpx_post):
    ret = script_runner.run(
        "kingspan-status",
        "--username=invalid@example.com",
        "--password=invalid",
        print_result=False,
    )

    assert not ret.success
    assert "invalid username or password" in ret.stderr
    assert ret.stdout == ""


@mark.script_launch_mode("inprocess")
def test_status(script_runner, mock_sync_httpx_post):
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


@mark.script_launch_mode("inprocess")
def test_debug(script_runner, mock_sync_httpx_post, mock_wsdl):
    ret = script_runner.run(
        "kingspan-status",
        "--username=test@example.com",
        "--password=s3cret",
        "--debug",
        "--api-version=CONNECT_V1",
        print_result=False,
    )
    assert ret.success
    output = [s.strip() for s in ret.stdout.split("\n")]
    assert output == VALID_STATUS
    stderr = [s.strip() for s in ret.stderr.split("\n")]
    assert stderr[0] == "DEBUG:connectsensor:Init API with version=CONNECT_V1"
    assert "'apiUserID': '*redacted*'" in stderr[1]
    assert "'emailAddress': '*redacted*'" in stderr[1]
