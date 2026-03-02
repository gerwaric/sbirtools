"""CLI: sbirtools-download-data to cache the SBIR CSV."""

import sys

from sbirtools._data import download_csv, get_csv_path


def main() -> None:
    """Download the SBIR CSV from the given URL to the cache directory."""
    if len(sys.argv) < 2:
        print(
            "Usage: sbirtools-download-data <URL>",
            file=sys.stderr,
        )
        print(
            f"  Saves to {get_csv_path()} (override with SBIRTOOLS_CACHE_DIR)",
            file=sys.stderr,
        )
        sys.exit(1)
    url = sys.argv[1].strip()
    if not url:
        print("Error: URL must not be empty.", file=sys.stderr)
        sys.exit(1)
    try:
        path = download_csv(url)
        print(f"SBIR data cached at {path}", file=sys.stderr)
    except OSError as e:
        print(f"Error downloading: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
