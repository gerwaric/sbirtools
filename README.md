# sbirtools

A hardened Python sandbox with SBIR awards data for AI agents. Execute agent-supplied code safely with a preloaded pandas DataFrame of SBIR awards (~250–300 MB in memory).

## Motivation

The official SBIR website provides an API that allows end-customers to search SBIR awards data: https://www.sbir.gov/api.

There is also a very useful MCP server that developers can use to give agents access to this data, such as https://github.com/shawndrake2/mcp-sba.

However, both of those tools are limited to by the SBIR's underlying API. This limits the searches you perform, and the API consumer has to manage paging through results while obeying API rate limits. This `sbirtools` packages make the entire SBIR awards database available to an agent as a `pandas` dataframe within a hardened Python sandbox. This allows agents to not only perform complex searches, but they use regular expressions and perform general calculations on the results as needed.

The cost of this approach is keeping a 300MB file loaded into memory, but the benefit is nearly instant access and the ability to write python code to search, manipulate, and process this data with ease.

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

## Using sbirtools as an agent tool

Expose sbirtools as a **tool** your agent can call: the agent sends generated Python code; your tool runs it and returns the result. Use the built-in handlers so you don't have to write the wrapper or the tool description yourself.

### 1. Setup (once)

```bash
pip install sbirtools
sbirtools-download-data https://data.www.sbir.gov/awarddatapublic/award_data.csv
```

### 2. Choose a handler and register it

**Stateless (one-off runs):** Import `run_sbir_code` and pass it as your tool. Each call runs in a new process and loads the data.

```python
from sbirtools import run_sbir_code

# Register with your framework, e.g. tools=[run_sbir_code]
```

**Session-based (many runs per task):** Import `SessionTool`, create one per conversation or task, and pass its `run` method (or the instance itself if your framework calls the tool with `tool(code)`). The dataset stays in memory. Call `close()` when the task ends.

```python
from sbirtools import SessionTool

tool = SessionTool(timeout=30)
# Register with your framework, e.g. tools=[tool.run] or tools=[tool]
# When the task ends: tool.close()
```

### 3. Tool name and description

- **Name:** Use a name your framework expects (e.g. `run_sbir_code` or `query_award_data`). When using the importable handlers, the function or method name is often used automatically.
- **Description:** The handlers’ docstrings are written for the LLM. Most frameworks (OpenAI, LangChain, etc.) use the function’s or method’s docstring as the tool description, so you usually don’t need to paste one — just register the handler.

For the full list of DataFrame columns, see [docs/sample-sbir-awards.csv](docs/sample-sbir-awards.csv) or [DESIGN.md §5](docs/DESIGN.md).

### 4. Minimal example

```python
from sbirtools import run_sbir_code, SessionTool

# Stateless: pass the function
# your_framework.add_tool(run_sbir_code)

# Or session-based: create tool, pass tool.run or tool, then close when done
tool = SessionTool(timeout=30)
# your_framework.add_tool(tool.run)  # or tool if it accepts a callable
# ... run agent ...
tool.close()
```

- [Design](docs/DESIGN.md) — architecture, API, security layers, schema
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — phases and tasks
- [Sample CSV schema](docs/sample-sbir-awards.csv) — column reference

## Limitations

Execution is limited by a timeout (default 30s) and by process memory. There is no hard CPU limit, so very tight loops can consume CPU until the timeout. The full SBIR dataset is loaded into memory (~250–300 MB).
