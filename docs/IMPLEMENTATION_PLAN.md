# Implementation Plan: sbirtools

This plan breaks the work into ordered phases. Each phase produces testable outcomes before moving to the next.

---

## Phase 1: Project scaffold and data pipeline

**Goal:** Repo layout, build, and CSV download + cache + load into pandas, without sandbox.

### 1.1 Package scaffold

- [ ] Create `pyproject.toml` with package metadata, **Python 3.10+**, `pandas` as dependency, optional `requests` (or `urllib`) for download.
- [ ] Create package layout: `sbirtools/__init__.py`, `sbirtools/_data.py`, `sbirtools/_result.py`, `sbirtools/_sandbox.py` (stubs).
- [ ] Add a minimal `run(code: str) -> RunResult` in `__init__.py` that for now only returns a placeholder `RunResult` (e.g. stdout="", stderr="", success=True, error_message=None).
- [ ] Verify `pip install -e .` and `import sbirtools; sbirtools.run("1+1")` work.

### 1.2 URL configuration and cache path

- [ ] Define default CSV URL (e.g. env var `SBIRTOOLS_CSV_URL` or constant to be overridden later).
- [ ] Define cache directory: e.g. `~/.cache/sbirtools` or under package data; make it configurable.
- [ ] Implement in `_data.py`: `get_cache_path() -> Path`, `get_csv_url() -> str`.

### 1.3 Download and cache CSV

- [ ] Implement `download_csv_if_missing() -> Path`: if cache path does not exist or is empty, download from configured URL; return path to CSV file.
- [ ] Prefer standard library (`urllib.request`) to avoid extra dependency; optional `requests` for nicer error handling if desired.
- [ ] Add simple tests (e.g. mock URL or small local CSV) to verify download and cache behavior.

### 1.4 Load DataFrame

- [ ] Implement `load_sbir_dataframe() -> pd.DataFrame` in `_data.py`: call `download_csv_if_missing()`, then `pd.read_csv(path)`.
- [ ] Document expected columns (see `docs/sample-sbir-awards.csv` and DESIGN.md §5); add schema docstring in `_data.py` and agent-facing docstring.
- [ ] Optional: expose `get_sbir_dataframe()` in public API for testing or inspection; not required for agents.

**Exit criteria:** Install package; call `load_sbir_dataframe()` (with a test URL or local file) and get a pandas DataFrame. No sandbox yet.

---

## Phase 2: Sandbox execution (hardened)

**Goal:** Execute user code in an isolated environment with resource limits and a restricted globals dict that includes the SBIR DataFrame.

### 2.1 Execution model

- [ ] Choose execution strategy (recommended: **subprocess** running a small runner script that receives code and returns serialized result).
- [ ] Alternative: in-process with `RestrictedPython` or `ast`-based restriction; document trade-offs (simplicity vs. strength of isolation).
- [ ] Implement runner that: builds globals (DataFrame, pandas, numpy, allowed stdlib), executes `code`, captures stdout/stderr, and returns last expression or return value plus success/error.

### 2.2 Restricted environment (security layer: import limits)

- [ ] Define whitelist of builtins and modules: **pandas**, numpy, `math`, `re`, `json`, `collections`, `datetime`, etc. No `os`, `subprocess`, `socket`, `open`.
- [ ] User code must not use `import` / `from ... import`; **AST check** (Phase 2.5) rejects those. Sandbox preloads only whitelisted modules into `globals()` before `exec`.
- [ ] Ensure `load_sbir_dataframe()` is called once and the DataFrame is injected as **`award_data`**.

### 2.3 Resource limits

- [ ] Apply timeout (e.g. 30s default) to the subprocess or in-process execution.
- [ ] Optional: memory limit via `resource` (Unix) or subprocess wrapper; document platform support.
- [ ] On timeout or failure, return `RunResult(success=False, stdout="", stderr="...", error_message="Timeout", ...)`.

### 2.4 Result (stdout only)

- [ ] Define `RunResult` in `_result.py` (dataclass): `stdout`, `stderr`, `success`, `error_message`. No `result` field; primary output is stdout.
- [ ] Subprocess runner captures stdout/stderr and prints a single result payload (e.g. JSON) to a dedicated channel; parent parses and constructs `RunResult`.

### 2.5 AST checks (security layer)

- [ ] Before execution, parse code with `ast` and reject if it contains: `import`, `from ... import`, `open`, `exec`, `eval`, `compile(..., 'exec')`, or attribute access to `__builtins__`, `__globals__`, `__import__`, etc. Maintain a small blocklist of forbidden names and node types.
- [ ] On reject, return `RunResult(success=False, error_message="Forbidden construct: ...")` without executing.

### 2.6 Size sanity checks (security layer)

- [ ] Enforce **max code string length** (e.g. 50 KB or 100 KB); reject with clear error if exceeded.
- [ ] Enforce **max captured output length** (stdout): cap at a fixed size (e.g. 1 MB); if exceeded, truncate and append a note (e.g. `"\n... [output truncated]"`).
- [ ] **Do not** cap DataFrame size: load the entire CSV in `load_sbir_dataframe()` (~250–300 MB in memory); document memory expectation in docs.

**Exit criteria:** `run("print(award_data.head())")` returns a RunResult with stdout containing the head output and success=True; `run("open('/etc/passwd')")` is rejected by AST or fails in sandbox; timeout works.

---

## Phase 3: Public API and docstrings

**Goal:** Stable public API, clear docstrings for agents, and install-time data option.

### 3.1 Main function signature and docstring

- [ ] Finalize `run(code: str, timeout: float = 30.0, **kwargs) -> RunResult` (add timeout or other knobs as needed).
- [ ] Write docstring that explains:
  - Execution is sandboxed (no network, no filesystem); primary output is stdout.
  - A pandas DataFrame **`award_data`** is available (SBIR awards data).
  - Column names and brief semantics (or “see docs” link).
  - **Preloaded whitelist** (no `import` in user code): e.g. **pandas**, **math**, numpy, re, json, collections, datetime; list in docstring.
- [ ] Add module-level docstring or README section that agents can use as context.

### 3.2 Data download CLI

- [x] CLI **`sbirtools-download-data`** takes the **URL as the first argument** (e.g. `sbirtools-download-data <URL>`). Calls `download_csv(url)` and saves to **`<SBIRTOOLS_CACHE_DIR>/award_data.csv`** (default `~/.cache/sbirtools/award_data.csv`).
- [x] Document in README: usage `sbirtools-download-data <URL>`, where the cache lives, and that the cache filename is `award_data.csv`.

### 3.3 README and minimal docs

- [ ] README: purpose, install, run `sbirtools-download-data` to cache data, quick example `run("print(award_data.columns.tolist())")`, link to design/doc for schema and sandbox rules.
- [ ] Optional: add a `docs/` section for “Schema of SBIR DataFrame” (columns from `docs/sample-sbir-awards.csv` / DESIGN.md §5).

**Exit criteria:** Agent-facing docstring and README are sufficient to write correct sandbox code; install with optional data works; `run(code)` and **SandboxSession** are the main entry points returning raw RunResult.

---

## Phase 3b: Persistent session (SandboxSession) — implemented

**Goal:** Keep the DataFrame in memory across multiple runs by using a long-lived worker process.

- [x] **Worker process** (`_worker.py`): Load `award_data` once via `_build_sandbox_globals()`, then loop: read length-prefixed code from stdin (4-byte length + UTF-8 payload), validate AST/length, run in sandbox globals, write one JSON result line to stdout.
- [x] **SandboxSession** (`_sandbox.py`): Start worker on first `run()`, reuse for subsequent `session.run(code)`. Send code length-prefixed over stdin; read one JSON line from stdout with timeout (thread + join). On timeout, kill worker; next `run()` starts a new worker. Thread lock for single-threaded use. `close()` stops the worker; context manager support.
- [x] Export **SandboxSession** from `__init__.py`; document in README with example.
- [x] Tests in `tests/test_session.py`: session reuses worker, rejects forbidden code, `close()` idempotent.

**Exit criteria:** `with SandboxSession() as s: s.run("print(len(award_data))")` succeeds; data is loaded once per session.

---

## Phase 4: Testing and hardening

**Goal:** Regression tests, edge cases, and a quick security review.

### 4.1 Unit tests

- [ ] Tests for `_data`: cache path, download (mocked), `load_sbir_dataframe()` with fixture CSV.
- [ ] Tests for `_result`: RunResult construction and serialization.
- [ ] Tests for `run()`: simple expression, DataFrame access, timeout, forbidden builtins (expect failure or safe behavior).

### 4.2 Integration test

- [ ] One end-to-end test: install, load fixture CSV (e.g. `docs/sample-sbir-awards.csv`), `run("print(award_data.shape)")` and assert stdout contains shape.

### 4.3 Security-minded checks

- [ ] Try `run("__import__('os').system('id')")` and similar; ensure they do not escape sandbox.
- [ ] Document known limitations (e.g. CPU DoS if no hard CPU limit, or that memory is only limited by process).

**Exit criteria:** Test suite passes; README and design doc are updated with any new constraints or options.

---

## Dependency order

```
Phase 1 (scaffold + data)  →  Phase 2 (sandbox)  →  Phase 3 (API + docs)  →  Phase 4 (tests + hardening)
```

- Phase 2 depends on Phase 1 (need DataFrame and cache before injecting into sandbox).
- Phase 3 can start once Phase 2 has a working `run()`; docstrings can be refined after Phase 4.
- Phase 4 can be partially done in parallel with Phase 3 (e.g. unit tests for data and result in Phase 1/2).

---

## Suggested implementation order (checklist)

1. **Phase 1.1** – Scaffold  
2. **Phase 1.2–1.4** – Data pipeline (config, download, load)  
3. **Phase 2.1** – Execution model (subprocess vs in-process)  
4. **Phase 2.2–2.4** – Restricted env, limits, RunResult  
5. **Phase 3.1–3.3** – Docstrings, install-time data, README  
6. **Phase 4.1–4.3** – Tests and security checks  

---

## Resolved decisions (from design)

- **DataFrame name:** `award_data`.
- **Cache filename:** `award_data.csv` in cache directory.
- **Data download:** CLI `sbirtools-download-data <URL>` (URL as first argument); documented in package docs.
- **Python:** 3.10+.
- **Output:** stdout only (no return-value serialization).
- **Security:** Multiple layers — AST checks, preloaded whitelist (pandas, math, etc.; no `import` in user code), size limits (max code length, max stdout length; full CSV loaded, no DataFrame cap ~250–300 MB), subprocess + timeout.
- **Persistent session:** SandboxSession keeps a long-lived worker that loads data once and serves multiple `session.run(code)` calls; use for agents that run code often.
- **Schema:** See `docs/sample-sbir-awards.csv` and DESIGN.md §5; document in docstring.

## Open points to resolve during implementation

- **Exact CSV URL:** to be set when source is fixed; configurable via `SBIRTOOLS_CSV_URL`.
- **Subprocess vs RestrictedPython:** subprocess recommended for isolation; decide in Phase 2.1.
- **Exact size limits:** max code length (e.g. 50–100 KB) and max captured stdout length (e.g. 1 MB, truncate with note). No DataFrame cap; full CSV (~250–300 MB) loaded.
