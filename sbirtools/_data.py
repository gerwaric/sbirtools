# Data pipeline: URL config, download, cache, load DataFrame.
# Schema: see docs/sample-sbir-awards.csv and DESIGN.md §5.

import os
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd

# Default CSV URL when source is fixed; override with SBIRTOOLS_CSV_URL.
DEFAULT_CSV_URL = ""

# Cache filename inside cache directory.
CSV_FILENAME = "award_data.csv"


def get_cache_path() -> Path:
    """Return the cache directory for the SBIR CSV (e.g. ~/.cache/sbirtools)."""
    if "SBIRTOOLS_CACHE_DIR" in os.environ:
        return Path(os.environ["SBIRTOOLS_CACHE_DIR"]).resolve()
    return Path.home() / ".cache" / "sbirtools"


def get_csv_url() -> str:
    """Return the URL to download the SBIR CSV from. Set SBIRTOOLS_CSV_URL to override."""
    return os.environ.get("SBIRTOOLS_CSV_URL", DEFAULT_CSV_URL).strip()


def get_csv_path() -> Path:
    """Return the path where the cached CSV file is stored."""
    return get_cache_path() / CSV_FILENAME


def download_csv(url: str) -> Path:
    """
    Download the SBIR CSV from the given URL to the cache directory.
    Saves to <SBIRTOOLS_CACHE_DIR>/award_data.csv (default ~/.cache/sbirtools/award_data.csv).
    Returns the path to the saved file.
    """
    path = get_csv_path()
    cache_dir = get_cache_path()
    cache_dir.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, path)
    return path


def download_csv_if_missing() -> Path:
    """
    If the cache path does not exist, download the CSV from the configured URL.
    Returns the path to the CSV file. Raises if URL is not set and file is missing.
    """
    path = get_csv_path()
    if path.exists():
        return path
    url = get_csv_url()
    if not url:
        raise ValueError(
            "SBIR CSV not cached and SBIRTOOLS_CSV_URL is not set. "
            "Set SBIRTOOLS_CSV_URL and run sbirtools-download-data to cache the data."
        )
    cache_dir = get_cache_path()
    cache_dir.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, path)
    return path


def load_sbir_dataframe() -> pd.DataFrame:
    """
    Load the SBIR awards DataFrame from the cache (or SBIRTOOLS_CSV_PATH if set).
    Full CSV is loaded (~250–300 MB in memory). No row/column cap.
    Columns: Company, Award Title, Agency, Branch, Phase, Program, Agency Tracking Number,
    Contract, Proposal Award Date, Contract End Date, Solicitation Number, Solicitation Year,
    Solicitation Close Date, Proposal Receipt Date, Date of Notification, Topic Code,
    Award Year, Award Amount, Duns, HUBZone Owned, Socially and Economically Disadvantaged,
    Women Owned, Number Employees, Company Website, Address1, Address2, City, State, Zip,
    Abstract, Contact Name, Contact Title, Contact Phone, Contact Email, PI Name, PI Title,
    PI Phone, PI Email, RI Name, RI POC Name, RI POC Phone.
    """
    if "SBIRTOOLS_CSV_PATH" in os.environ:
        path = Path(os.environ["SBIRTOOLS_CSV_PATH"]).resolve()
    else:
        path = get_csv_path()
    if not path.exists():
        raise FileNotFoundError(
            f"SBIR CSV not found at {path}. "
            "Run 'sbirtools-download-data' to download it, or set SBIRTOOLS_CSV_PATH to a local file."
        )
    return pd.read_csv(path, encoding="utf-8", encoding_errors="replace")
