"""Security-minded tests: ensure escape attempts are rejected or contained."""

import pytest

from sbirtools import run


def test_run_rejects_import_builtins_escape():
    """__import__('os').system is not allowed (AST rejects __import__)."""
    r = run("__import__('os').system('id')")
    assert not r.success


def test_run_rejects_getattr_builtins():
    """getattr(__builtins__, ...) style escape is rejected."""
    r = run("getattr(__builtins__, '__import__')('os')")
    assert not r.success


def test_run_rejects_double_underscore_globals():
    """Access to __globals__ is rejected."""
    r = run("(lambda: None).__globals__")
    assert not r.success


def test_run_rejects_eval():
    r = run("eval('1')")
    assert not r.success


def test_run_rejects_compile_exec():
    r = run("compile('pass', '<s>', 'exec')")
    assert not r.success
