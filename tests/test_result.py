"""Tests for RunResult."""

import pytest

from sbirtools._result import RunResult


def test_run_result_success():
    r = RunResult(stdout="ok", stderr="", success=True, error_message=None)
    assert r.stdout == "ok"
    assert r.success
    assert r.error_message is None


def test_run_result_failure():
    r = RunResult(stdout="", stderr="err", success=False, error_message="Bad")
    assert not r.success
    assert r.error_message == "Bad"


def test_run_result_frozen():
    r = RunResult(stdout="x", stderr="", success=True, error_message=None)
    with pytest.raises((AttributeError, Exception)):
        r.stdout = "y"  # type: ignore[misc]


def test_run_result_optional_error_message():
    r = RunResult(stdout="", stderr="", success=True)
    assert r.error_message is None
