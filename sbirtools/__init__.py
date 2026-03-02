"""sbirtools: hardened Python sandbox with SBIR awards data for AI agents."""

from sbirtools._result import RunResult
from sbirtools._sandbox import run_sandbox, SandboxSession


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


__all__ = ["run", "RunResult", "SandboxSession"]
