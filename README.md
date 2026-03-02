# sbirtools

A hardened Python sandbox with SBIR awards data for AI agents. Execute agent-supplied code safely with a preloaded pandas DataFrame of SBIR awards (~250–300 MB in memory).

## Install

```bash
pip install sbirtools
```

Requires Python 3.10+.

## Cache the SBIR data

Before using `run()`, download the CSV into the cache (or set `SBIRTOOLS_CSV_PATH` to a local file):

```bash
sbirtools-download-data <URL>
```

Example: `sbirtools-download-data https://data.www.sbir.gov/awarddatapublic/award_data.csv`

The file is saved to `~/.cache/sbirtools/award_data.csv` (override the directory with `SBIRTOOLS_CACHE_DIR`).

## Usage

```python
import sbirtools

result = sbirtools.run("print(award_data.columns.tolist())")
print(result.stdout)   # primary output
print(result.success) # True/False
```

Code runs in a sandbox: no network or filesystem access. Use `print()` for output. A DataFrame **`award_data`** and a whitelist of modules (pandas, math, re, json, etc.) are preloaded; `import` is not allowed.

### Persistent session (data loaded once)

If you call `run()` many times, use **`SandboxSession`** so the CSV is loaded once and kept in memory in a long-lived worker process:

```python
import sbirtools

with sbirtools.SandboxSession(timeout=30) as session:
    r1 = session.run("print(len(award_data))")
    r2 = session.run("print(award_data['Agency'].nunique())")
    print(r1.stdout, r2.stdout)
```

Each `run()` reuses the same worker; call `session.close()` or exit the `with` block to stop the worker.

- [Design](docs/DESIGN.md) — architecture, API, security layers, schema
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — phases and tasks
- [Sample CSV schema](docs/sample-sbir-awards.csv) — column reference

## Limitations

Execution is limited by a timeout (default 30s) and by process memory. There is no hard CPU limit, so very tight loops can consume CPU until the timeout. The full SBIR dataset is loaded into memory (~250–300 MB).
