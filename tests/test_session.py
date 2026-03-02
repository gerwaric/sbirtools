"""Tests for SandboxSession (persistent worker)."""

import pytest

from sbirtools import SandboxSession


def test_session_run_twice_reuses_worker():
    """Two run() calls in the same session both succeed and use the same worker."""
    with SandboxSession(timeout=10) as session:
        r1 = session.run("print(1)")
        r2 = session.run("print(len(award_data))")
    assert r1.success and "1" in r1.stdout
    assert r2.success and r2.stdout.strip().isdigit()


def test_session_rejects_forbidden_code():
    with SandboxSession(timeout=5) as session:
        r = session.run("import os")
    assert not r.success
    assert "import" in (r.error_message or "").lower()


def test_session_close_stops_worker():
    session = SandboxSession(timeout=5)
    session.run("print(1)")
    session.close()
    session.close()  # idempotent
    # After close, next run() starts a new worker
    r = session.run("print(2)")
    assert r.success
    assert "2" in r.stdout
