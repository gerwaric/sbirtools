"""sbirtools: hardened Python sandbox with SBIR awards data for AI agents."""

from sbirtools._result import RunResult
from sbirtools._sandbox import (
    SandboxSession,
    SessionTool,
    run_sandbox,
)
from sbirtools._sandbox import _TOOL_DESCRIPTION


def run(code: str, timeout: float = 30.0, **kwargs) -> RunResult:
    """Execute Python code in a hardened sandbox with SBIR awards data available.

    Execution is sandboxed: no network or filesystem access. Use print() to produce
    output; the primary result is captured in RunResult.stdout.

    A pandas DataFrame named ``award_data`` is preloaded (SBIR awards data).
    Columns: Company, Award Title, Agency, Branch, Phase, Program, Agency Tracking Number,
    Contract, Proposal Award Date, Contract End Date, Solicitation Number, Solicitation Year,
    Solicitation Close Date, Proposal Receipt Date, Date of Notification, Topic Code,
    Award Year, Award Amount, Duns, HUBZone Owned, Socially and Economically Disadvantaged,
    Women Owned, Number Employees, Company Website, Address1, Address2, City, State, Zip,
    Abstract, Contact Name, Contact Title, Contact Phone, Contact Email, PI Name, PI Title,
    PI Phone, PI Email, RI Name, RI POC Name, RI POC Phone.
    See docs/sample-sbir-awards.csv and DESIGN.md for schema details.

    Preloaded whitelist (no ``import`` in user code): pandas, numpy (as np), math, re, json,
    collections, datetime, and safe builtins (print, len, list, dict, range, etc.).
    open, exec, eval, compile, and import are not allowed.

    Args:
        code: Python code to run in the sandbox.
        timeout: Maximum execution time in seconds (default 30).

    Returns:
        RunResult with stdout, stderr, success, and error_message.
    """
    return run_sandbox(code, timeout=timeout)


def run_sbir_code(code: str, timeout: float = 30.0) -> str:
    """Run Python code against the SBIR awards dataset and return the result as a string.

    Use this as your agent tool handler (stateless: each call loads the data in a new process).
    Many frameworks use this function's docstring as the tool description for the LLM.
    """
    result = run_sandbox(code, timeout=timeout)
    if result.success:
        return result.stdout
    parts = [f"Error: {result.error_message}"] if result.error_message else []
    if result.stderr:
        parts.append(result.stderr.strip())
    return "\n".join(parts) if parts else "Execution failed."


run_sbir_code.__doc__ = (
    "Run Python code against the SBIR awards dataset and return the result as a string.\n\n"
    + _TOOL_DESCRIPTION
)


__all__ = ["run", "RunResult", "SandboxSession", "SessionTool", "run_sbir_code"]
