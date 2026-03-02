"""Tests for _data module."""

from pathlib import Path

import pytest

from sbirtools._data import (
    get_cache_path,
    get_csv_path,
    get_csv_url,
    load_sbir_dataframe,
)


def test_get_cache_path_default(monkeypatch):
    """Without SBIRTOOLS_CACHE_DIR, returns ~/.cache/sbirtools."""
    monkeypatch.delenv("SBIRTOOLS_CACHE_DIR", raising=False)
    p = get_cache_path()
    assert p.name == "sbirtools"
    assert ".cache" in p.parts


def test_get_cache_path_override(monkeypatch, tmp_path):
    """With SBIRTOOLS_CACHE_DIR, returns that path."""
    monkeypatch.setenv("SBIRTOOLS_CACHE_DIR", str(tmp_path))
    assert get_cache_path() == tmp_path.resolve()


def test_get_csv_path():
    """CSV path is cache_dir / award_data.csv."""
    p = get_csv_path()
    assert p.name == "award_data.csv"


def test_get_csv_url_default(monkeypatch):
    """Without SBIRTOOLS_CSV_URL, returns default (empty or configured)."""
    monkeypatch.delenv("SBIRTOOLS_CSV_URL", raising=False)
    url = get_csv_url()
    assert isinstance(url, str)


def test_get_csv_url_override(monkeypatch):
    """With SBIRTOOLS_CSV_URL, returns that URL."""
    monkeypatch.setenv("SBIRTOOLS_CSV_URL", "https://example.com/data.csv")
    assert get_csv_url() == "https://example.com/data.csv"


def test_load_sbir_dataframe_with_fixture():
    """load_sbir_dataframe returns a DataFrame when SBIRTOOLS_CSV_PATH points to sample."""
    df = load_sbir_dataframe()
    assert df.shape[0] >= 1
    assert "Company" in df.columns
    assert "Award Title" in df.columns


def test_load_sbir_dataframe_missing_raises(monkeypatch):
    """When path does not exist, raises FileNotFoundError with helpful message."""
    monkeypatch.setenv("SBIRTOOLS_CSV_PATH", "/nonexistent/sbir.csv")
    with pytest.raises(FileNotFoundError) as exc_info:
        load_sbir_dataframe()
    assert "sbirtools-download-data" in str(exc_info.value)
