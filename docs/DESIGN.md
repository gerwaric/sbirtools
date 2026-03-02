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
│            │  - sbir_awards (DataFrame),  │                     │
│            │    pandas, etc. No network   │                     │
│            └──────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

- **Data download:** Users run a **CLI** (e.g. `sbirtools-download-data`) to download the CSV from a configured URL into a cache directory. This is documented in the package docs; no automatic install-time download. Pandas is a dependency; the DataFrame is built when the sandbox is first used (or at import).
- **Run time:** The main function builds an execution environment that includes the SBIR DataFrame (as `sbir_awards`) and other allowed builtins/modules, runs the user code in the sandbox, and returns a single raw result object (stdout is the primary output).

---

## 3. Key design decisions (accepted)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API shape | One main function returning a raw result | Simple for agents; no hidden formatting. Caller decides how to present stdout/stderr/result. |
| Data at install | CSV downloadable and cached at install (or first use) | Reproducible builds; no mandatory network at run time. |
| Data in sandbox | Single pandas DataFrame named **`sbir_awards`** | Docstring explains columns and usage. |
| Sandbox model | Hardened execution with **multiple security layers** (AST checks, import limits, size sanity checks, subprocess/resource limits) | Protect against both accidental misuse and malicious code. |
| Python version | **3.10+** | Modern and very common. |
| Primary output | **Stdout** only (no return-value serialization from executed code) | Simple; agent uses printed output. |

---

## 4. Public API

### 4.1 Main entry point

- **`run(code: str, **kwargs) -> RunResult`**  
  Execute `code` in the sandbox with the SBIR DataFrame and allowed libraries available. Returns a raw result object (see below). Any extra kwargs can be reserved for future options (timeout, memory limit, etc.).

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
- That a **pandas DataFrame** named **`sbir_awards`** is preloaded (SBIR awards data).
- **Column names and semantics** (see §5 Schema below) so the agent can generate correct code.
- That a **preloaded whitelist** of modules is available (e.g. **pandas**, **math**, numpy, re, json, collections, datetime) and that `import` is not allowed in user code; the docstring should list or reference this whitelist.

---

## 5. Data pipeline

1. **URL configuration**  
   Single CSV URL, configurable (e.g. environment variable or config file at install/build time). Default can point to a specific SBIR data source; override for testing or mirrors.

2. **Download and cache**  
   - Users run a **CLI** (e.g. `sbirtools-download-data`) to download the CSV to a known cache location (e.g. `~/.cache/sbirtools`). Document this in the package README and docs.  
   - If cache is missing at run time, `run()` can fail with a clear error telling the user to run the CLI first (or we optionally download on first use; TBD).

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
  __init__.py          # run(), RunResult, get_df() if needed
  _sandbox.py          # execution and env setup
  _data.py             # URL config, download, cache, load DataFrame
  _result.py           # RunResult and helpers
  pyproject.toml       # deps: pandas, optional requests for download
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
- Result is returned as a single raw object (RunResult) with stdout (primary output), stderr, success, and error_message.
- Docstring and docs give an agent enough information to write correct, sandbox-compliant code using the DataFrame.
