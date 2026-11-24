"""Tests for the kingspan-status CLI entrypoint."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from tests.mock_data import VALID_STATUS

if TYPE_CHECKING:
    from pytest_console_scripts import ScriptRunner
    from pytest_mock import MockerFixture


@pytest.mark.script_launch_mode("subprocess")
def test_help(script_runner: ScriptRunner) -> None:
    """Verify CLI fails with usage output when required arguments are omitted."""
    ret = script_runner.run("kingspan-status", print_result=False)
    assert not ret.success
    assert "usage: kingspan-status [-h]" in ret.stderr
    assert ret.stdout == ""


@pytest.mark.script_launch_mode("subprocess")
def test_help_verbose(script_runner: ScriptRunner) -> None:
    """Verify CLI --help flag outputs usage and option descriptions."""
    ret = script_runner.run("kingspan-status", "--help", print_result=False)
    assert ret.success
    assert "usage: kingspan-status [-h]" in ret.stdout
    assert "username USERNAME" in ret.stdout
    assert ret.stderr == ""


@pytest.mark.script_launch_mode("inprocess")
@pytest.mark.usefixtures("mock_sync_httpx_post")
def test_help_invalid_credentials(script_runner: ScriptRunner) -> None:
    """Verify CLI reports authentication failures cleanly to stderr."""
    ret = script_runner.run(
        "kingspan-status",
        "--username=invalid@example.com",
        "--password=invalid",
        print_result=False,
    )

    assert not ret.success
    assert "invalid username or password" in ret.stderr
    assert ret.stdout == ""


@pytest.mark.script_launch_mode("inprocess")
def test_help_invalid_error(script_runner: ScriptRunner, mocker: MockerFixture) -> None:
    """Verify CLI reports general API errors cleanly to stderr."""
    mock_response = httpx.Response(
        status_code=200,
        content=json.dumps(
            {"apiResult": {"code": 1, "description": "test API error"}},
        ).encode("utf-8"),
    )
    mocker.patch.object(httpx.Client, "post", return_value=mock_response)

    ret = script_runner.run(
        "kingspan-status",
        "--username=invalid@example.com",
        "--password=invalid",
        print_result=False,
    )

    assert not ret.success
    assert "Kingspan API error: test API error" in ret.stderr
    assert ret.stdout == ""


@pytest.mark.script_launch_mode("inprocess")
@pytest.mark.usefixtures("mock_sync_httpx_post")
def test_status(script_runner: ScriptRunner) -> None:
    """Verify CLI formats tank status and history output as expected."""
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


@pytest.mark.script_launch_mode("inprocess")
@pytest.mark.usefixtures("mock_sync_httpx_post", "mock_wsdl")
def test_debug(script_runner: ScriptRunner) -> None:
    """Verify CLI --debug flag emits redacted debug logs to stderr."""
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


@pytest.mark.script_launch_mode("subprocess")
def test_main(script_runner: ScriptRunner) -> None:
    """Verify package module execution via python -m."""
    ret = script_runner.run(
        ["python3", "-m", "connectsensor._kingspan_status", "--help"],
        print_result=False,
    )
    assert ret.success
    assert "[-h] --username" in ret.stdout
    assert ret.stderr == ""
