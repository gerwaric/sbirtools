"""Tests for sbirtools."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def use_sample_csv(monkeypatch):
    """Use the sample SBIR CSV for all tests that need data."""
    sample = Path(__file__).resolve().parent.parent / "docs" / "sample-sbir-awards.csv"
    if sample.exists():
        monkeypatch.setenv("SBIRTOOLS_CSV_PATH", str(sample))
