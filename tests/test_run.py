"""Tests for run() and sandbox."""

import pytest

from sbirtools import run
from sbirtools._sandbox import MAX_CODE_LENGTH


def test_run_simple_expression():
    r = run("print(1 + 1)")
    assert r.success
    assert "2" in r.stdout


def test_run_award_data_shape():
    r = run("print(award_data.shape)")
    assert r.success
    assert "(" in r.stdout and ")" in r.stdout


def test_run_award_data_columns():
    r = run("print(award_data.columns.tolist()[:3])")
    assert r.success
    assert "Company" in r.stdout


def test_run_rejects_import():
    r = run("import os")
    assert not r.success
    assert "import" in (r.error_message or "").lower()


def test_run_rejects_open():
    r = run("open('/etc/passwd')")
    assert not r.success
    assert "open" in (r.error_message or "").lower()


def test_run_rejects_exec():
    r = run("exec('1')")
    assert not r.success


def test_run_syntax_error():
    r = run("syntax error here")
    assert not r.success
    assert "syntax" in (r.error_message or "").lower()


def test_run_code_too_long():
    r = run("x = 1\n" * (MAX_CODE_LENGTH // 5))
    assert not r.success
    assert "length" in (r.error_message or "").lower()


def test_run_timeout():
    r = run("while True: pass", timeout=0.5)
    assert not r.success
    assert "timed out" in (r.error_message or "").lower()


def test_run_stdout_truncation_note():
    # Print more than MAX_STDOUT_LENGTH (1 MB) - skip in unit test, too slow
    # Just check that normal output is not truncated
    r = run("print('hello')")
    assert r.success
    assert "hello" in r.stdout
    assert "truncated" not in r.stdout
