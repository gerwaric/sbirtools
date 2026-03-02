# Design Document: sbirtools

## 1. Purpose and scope

**sbirtools** is an open-source Python package for builders of AI agents. It provides:

1. **A hardened Python sandbox** in which agent-supplied Python code can be executed safely.
2. **Local SBIR awards data** loaded from a configurable CSV URL, downloadable at install time and cached. The data is exposed inside the sandbox as a pandas DataFrame so agents can query and analyze it without network access at run time.

The package exposes **one main function** that accepts code and returns a **raw result** (stdout, stderr, success, and error info). The primary output for the executed code is **stdout**; the caller interprets it. Python version support: **3.10+** (modern and widely available).

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Caller (e.g. AI agent orchestration layer)                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ run(code: str) -> RunResult
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  sbirtools                                                      │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐ │
│  │  Sandbox runner     │  │  SBIR data loader                 │ │
│  │  - Isolated exec    │  │  - CSV from configured URL         │ │
│  │  - Resource limits  │  │  - Cached at install time          │ │
│  │  - Preloaded env    │  │  - pandas DataFrame in env         │ │
│  └─────────┬───────────┘  └──────────────┬───────────────────┘ │
│            │                              │                      │
│            └──────────────┬───────────────┘                      │
│                           ▼                                     │
│            ┌──────────────────────────────┐                     │
│            │  Execution environment       │                     │
│            │  - award_data (DataFrame),   │                     │
│            │    pandas, etc. No network   │                     │
│            └──────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

- **Data download:** Users run **`sbirtools-download-data <URL>`** (URL as first argument). The CSV is saved to `~/.cache/sbirtools/award_data.csv` (override directory with `SBIRTOOLS_CACHE_DIR`). No automatic install-time download. Pandas is a dependency; the DataFrame is built when the sandbox is first used (or when a persistent worker starts).
- **Run time:** The main function builds an execution environment that includes the SBIR DataFrame (as `award_data`) and other allowed builtins/modules, runs the user code in the sandbox, and returns a single raw result object (stdout is the primary output). Alternatively, **SandboxSession** keeps a long-lived worker process so the DataFrame is loaded once and reused across many `run()` calls.

---

## 3. Key design decisions (accepted)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API shape | One main function returning a raw result | Simple for agents; no hidden formatting. Caller decides how to present stdout/stderr/result. |
| Data at install | CSV downloadable and cached at install (or first use) | Reproducible builds; no mandatory network at run time. |
| Data in sandbox | Single pandas DataFrame named **`award_data`** | Docstring explains columns and usage. |
| Sandbox model | Hardened execution with **multiple security layers** (AST checks, import limits, size sanity checks, subprocess/resource limits) | Protect against both accidental misuse and malicious code. |
| Python version | **3.10+** | Modern and very common. |
| Primary output | **Stdout** only (no return-value serialization from executed code) | Simple; agent uses printed output. |

---

## 4. Public API

### 4.1 Entry points

- **`run(code: str, timeout: float = 30.0, **kwargs) -> RunResult`**  
  Execute `code` in a **one-off** subprocess with the SBIR DataFrame and allowed libraries available. Each call loads the data (or uses a fresh process). Returns a raw result object (see below). Use when you run code infrequently.

- **`SandboxSession(timeout: float = 30.0)`**  
  A **persistent** sandbox: a long-lived worker process loads `award_data` once and serves multiple `session.run(code)` calls. Use when you run code many times (e.g. an agent making repeated tool calls). Context manager: `with SandboxSession() as session: session.run(code)`. Call `session.close()` or exit the `with` block to stop the worker.

### 4.2 Result type

- **`RunResult`** (dataclass or similar) with:
  - **`stdout: str`** — primary output; the executed code should use `print()` to produce results.
  - **`stderr: str`**
  - **`success: bool`** — whether execution completed without exception.
  - **`error_message: Optional[str]`** — if execution failed.

No `result` field: we do not serialize return values from the sandbox. Agents use stdout and this metadata to decide what to show the user or how to retry.

### 4.3 Docstring for agents

The main function (and/or module) must document:

- That execution runs in a sandbox with **no network or filesystem access**.
- That a **pandas DataFrame** named **`award_data`** is preloaded (SBIR awards data).
- **Column names and semantics** (see §5 Schema below) so the agent can generate correct code.
- That a **preloaded whitelist** of modules is available (e.g. **pandas**, **math**, numpy, re, json, collections, datetime) and that `import` is not allowed in user code; the docstring should list or reference this whitelist.

---

## 5. Data pipeline

1. **URL configuration**  
   Single CSV URL, configurable (e.g. environment variable or config file at install/build time). Default can point to a specific SBIR data source; override for testing or mirrors.

2. **Download and cache**  
   - Users run **`sbirtools-download-data <URL>`** (URL as the first argument). The CSV is saved to **`<SBIRTOOLS_CACHE_DIR>/award_data.csv`** (default `~/.cache/sbirtools/award_data.csv`). Document in README.  
   - If the cache is missing at run time, `run()` (or the worker) fails with a clear error; the user can run the CLI or set `SBIRTOOLS_CSV_PATH` to a local file.

3. **Loading**  
   On first sandbox run (or at import), load the **entire** CSV from the cache path into a pandas DataFrame (~250–300 MB in memory). No row/column cap; the full dataset is available. That same DataFrame (or a copy per run for safety) is injected into the sandbox globals.

4. **Schema**  
   The SBIR awards CSV has the following columns (see `docs/sample-sbir-awards.csv` for a sample). Document in docstring and docs so the agent can generate correct code.

   **Columns:** `Company`, `Award Title`, `Agency`, `Branch`, `Phase`, `Program`, `Agency Tracking Number`, `Contract`, `Proposal Award Date`, `Contract End Date`, `Solicitation Number`, `Solicitation Year`, `Solicitation Close Date`, `Proposal Receipt Date`, `Date of Notification`, `Topic Code`, `Award Year`, `Award Amount`, `Duns`, `HUBZone Owned`, `Socially and Economically Disadvantaged`, `Women Owned`, `Number Employees`, `Company Website`, `Address1`, `Address2`, `City`, `State`, `Zip`, `Abstract`, `Contact Name`, `Contact Title`, `Contact Phone`, `Contact Email`, `PI Name`, `PI Title`, `PI Phone`, `PI Email`, `RI Name`, `RI POC Name`, `RI POC Phone`.

---

## 6. Sandbox constraints and security layers

We defend against **both accidental misuse and malicious code** with several layers:

1. **AST checks** — Before execution, reject code that uses forbidden constructs (e.g. `import` / `from ... import`, `open`, `exec`, `eval`, `compile` with `'exec'`, access to `__builtins__`/`__globals__`, etc.). Keeps the surface area small and blocks obvious escape paths.
2. **Preloaded whitelist** — User code cannot use `import` (AST rejects it). The sandbox **preloads** a fixed whitelist of modules: **pandas** (and its dependencies, e.g. numpy), **math**, and other safe stdlib (e.g. `re`, `json`, `collections`, `datetime`). No `os`, `subprocess`, `socket`, `open`, etc. The docstring documents this whitelist so agents know what is available.
3. **Size sanity checks** — **Max code string length** (e.g. 50–100 KB) and **max captured output length** (stdout truncated with a note if exceeded). The full CSV is loaded with no DataFrame size limit.
4. **Isolation and resource limits** — Run in a **subprocess** with timeout (and optionally memory/CPU limits) so that even if something slips through, impact is bounded.

Goals: no network, no filesystem write, no subprocess/shell from user code. Implementation details (exact AST rules, whitelist, and size limits) are in the implementation plan.

---

## 7. Package layout (conceptual)

```
sbirtools/
  __init__.py          # run(), RunResult, SandboxSession
  _sandbox.py          # run_sandbox(), SandboxSession, AST checks, one-shot runner
  _worker.py           # long-lived worker loop (load data once, run code via stdin/stdout)
  _data.py             # URL/cache config, download_csv(url), load_sbir_dataframe()
  _result.py           # RunResult
  _cli.py              # sbirtools-download-data entry point
  pyproject.toml       # deps: pandas; script: sbirtools-download-data
  README, LICENSE, docs/
```

Config (URL, cache path) can live in `_data.py` with overrides via env or a small config module.

---

## 8. Out of scope (for this design)

- Authentication to the CSV URL (assume public or pre-signed URL).
- Multiple datasets or multiple DataFrames in the same sandbox (single SBIR dataset only).
- Versioning of the CSV content (handled by URL or cache path if needed).
- Agent-facing UI or prompts; only the Python API and docstrings.

---

## 9. Success criteria

- Install (with optional data download) works on Linux/macOS/Windows.
- `run(code)` executes in a hardened environment with the SBIR DataFrame available.
- **SandboxSession** allows multiple `session.run(code)` calls with the DataFrame loaded once in a worker process.
- Result is returned as a single raw object (RunResult) with stdout (primary output), stderr, success, and error_message.
- Docstring and docs give an agent enough information to write correct, sandbox-compliant code using the DataFrame.
