# Sandbox: execution, AST checks, size limits, restricted env.

import ast
import json
import os
import subprocess
import sys
import threading
from io import StringIO
from pathlib import Path
from typing import Optional

from sbirtools._data import load_sbir_dataframe
from sbirtools._result import RunResult

# Size limits (design: max code 50–100 KB, max stdout 1 MB).
MAX_CODE_LENGTH = 100 * 1024  # 100 KB
MAX_STDOUT_LENGTH = 1024 * 1024  # 1 MB

# Forbidden builtin names (user code cannot call these).
FORBIDDEN_BUILTINS = frozenset(
    {"open", "exec", "eval", "compile", "__import__", "input", "file", "reload"}
)

# Forbidden attribute names (e.g. obj.__builtins__).
FORBIDDEN_ATTRS = frozenset(
    {"__builtins__", "__globals__", "__import__", "__subclasses__", "__bases__", "__mro__"}
)


class _ForbiddenNodeError(Exception):
    def __init__(self, msg: str, node: ast.AST):
        self.msg = msg
        self.node = node
        super().__init__(msg)


class _ASTChecker(ast.NodeVisitor):
    """Reject code that uses forbidden constructs (import, open, exec, etc.)."""

    def visit_Import(self, node: ast.Import) -> None:
        raise _ForbiddenNodeError("import statements are not allowed", node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        raise _ForbiddenNodeError("from ... import is not allowed", node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_BUILTINS:
                raise _ForbiddenNodeError(
                    f"'{node.func.id}' is not allowed in the sandbox", node
                )
            if node.func.id == "getattr" and len(node.args) >= 2:
                if isinstance(node.args[1], ast.Constant) and node.args[1].value in FORBIDDEN_ATTRS:
                    raise _ForbiddenNodeError(
                        "getattr with forbidden attribute is not allowed", node
                    )
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_ATTRS:
                raise _ForbiddenNodeError(
                    f"attribute '{node.func.attr}' is not allowed", node
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in FORBIDDEN_ATTRS:
            raise _ForbiddenNodeError(
                f"attribute access '.{node.attr}' is not allowed", node
            )
        self.generic_visit(node)


def _validate_code_ast(code: str) -> None:
    """Raise if code contains forbidden AST nodes."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e}") from e
    _ASTChecker().visit(tree)


def _build_sandbox_globals():  # noqa: C901
    """Build the globals dict for sandbox execution: whitelist + award_data."""
    import collections
    import datetime
    import json as json_mod
    import math
    import re

    import numpy as np
    import pandas as pd

    award_data = load_sbir_dataframe()

    # Safe subset of builtins (no open, exec, eval, compile, __import__, input, etc.).
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bin": bin,
        "bool": bool,
        "bytes": bytes,
        "chr": chr,
        "dict": dict,
        "divmod": divmod,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "hash": hash,
        "hex": hex,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "oct": oct,
        "ord": ord,
        "pow": pow,
        "print": print,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "round": round,
        "set": set,
        "slice": slice,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "type": type,
        "zip": zip,
        "None": None,
        "True": True,
        "False": False,
    }

    return {
        **safe_builtins,
        "pandas": pd,
        "pd": pd,
        "numpy": np,
        "np": np,
        "math": math,
        "re": re,
        "json": json_mod,
        "collections": collections,
        "datetime": datetime,
        "award_data": award_data,
    }


def _run_in_process() -> None:
    """
    Run in a subprocess: read code from stdin, execute in sandbox, write
    JSON result to stderr. Used by run() via subprocess.
    """
    code = sys.stdin.read()
    out_buf = StringIO()
    err_buf = StringIO()
    try:
        gl = _build_sandbox_globals()
        # Redirect stdout/stderr for user code.
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out_buf, err_buf
        try:
            exec(code, gl)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        stdout_str = out_buf.getvalue()
        stderr_str = err_buf.getvalue()
        if len(stdout_str) > MAX_STDOUT_LENGTH:
            stdout_str = (
                stdout_str[:MAX_STDOUT_LENGTH]
                + "\n... [output truncated]\n"
            )
        result = {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "success": True,
            "error_message": None,
        }
    except Exception as e:
        result = {
            "stdout": out_buf.getvalue()[:MAX_STDOUT_LENGTH],
            "stderr": err_buf.getvalue(),
            "success": False,
            "error_message": f"{type(e).__name__}: {e}",
        }
        if len(result["stdout"]) == MAX_STDOUT_LENGTH:
            result["stdout"] += "\n... [output truncated]\n"
    # Write result to stderr so parent can capture it (user stdout is in the JSON).
    print(json.dumps(result), file=sys.stderr)


def run_sandbox(
    code: str,
    timeout: float = 30.0,
) -> RunResult:
    """
    Execute code in a sandboxed subprocess with award_data and whitelisted modules.
    Returns RunResult with stdout, stderr, success, error_message.
    """
    if len(code) > MAX_CODE_LENGTH:
        return RunResult(
            stdout="",
            stderr="",
            success=False,
            error_message=f"Code exceeds maximum length ({MAX_CODE_LENGTH} bytes).",
        )
    try:
        _validate_code_ast(code)
    except _ForbiddenNodeError as e:
        return RunResult(
            stdout="",
            stderr="",
            success=False,
            error_message=f"Forbidden construct: {e.msg}",
        )
    except ValueError as e:
        return RunResult(
            stdout="",
            stderr="",
            success=False,
            error_message=str(e),
        )

    exe = sys.executable
    cmd = [exe, "-c", "from sbirtools._sandbox import _run_in_process; _run_in_process()"]
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd(),
            env=os.environ.copy(),
        )
        stdout_bytes, stderr_bytes = proc.communicate(input=code.encode("utf-8"), timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return RunResult(
            stdout="",
            stderr="",
            success=False,
            error_message=f"Execution timed out after {timeout}s.",
        )
    except FileNotFoundError:
        return RunResult(
            stdout="",
            stderr="",
            success=False,
            error_message="Could not start Python subprocess.",
        )

    # Result payload is on stderr (JSON, usually last line).
    stderr_str = stderr_bytes.decode("utf-8", errors="replace")
    payload = None
    for line in reversed(stderr_str.strip().split("\n")):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if payload is None:
        try:
            payload = json.loads(stderr_str)
        except json.JSONDecodeError:
            return RunResult(
                stdout="",
                stderr=stderr_str,
                success=False,
                error_message="Sandbox did not return a valid result.",
            )
    return RunResult(
        stdout=payload.get("stdout", ""),
        stderr=payload.get("stderr", ""),
        success=payload.get("success", False),
        error_message=payload.get("error_message"),
    )


class SandboxSession:
    """
    Long-lived sandbox session: the award_data DataFrame is loaded once in a worker
    process and reused for every run(). Use this when you call run() many times to
    avoid reloading the CSV each time.
    """

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._process: Optional[subprocess.Popen] = None
        self._stdin = None
        self._stdout = None
        self._lock = threading.Lock()

    def _ensure_worker(self) -> None:
        if self._process is not None and self._process.poll() is not None:
            self._process = None
            self._stdin = self._stdout = None
        if self._process is None:
            self._process = subprocess.Popen(
                [sys.executable, "-c", "from sbirtools._worker import main; main()"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.getcwd(),
                env=os.environ.copy(),
            )
            self._stdin = self._process.stdin
            self._stdout = self._process.stdout

    def run(self, code: str, timeout: Optional[float] = None) -> RunResult:
        """Run code in the persistent worker. Uses session timeout if timeout is None."""
        if len(code) > MAX_CODE_LENGTH:
            return RunResult(
                stdout="",
                stderr="",
                success=False,
                error_message=f"Code exceeds maximum length ({MAX_CODE_LENGTH} bytes).",
            )
        try:
            _validate_code_ast(code)
        except _ForbiddenNodeError as e:
            return RunResult(
                stdout="",
                stderr="",
                success=False,
                error_message=f"Forbidden construct: {e.msg}",
            )
        except ValueError as e:
            return RunResult(
                stdout="",
                stderr="",
                success=False,
                error_message=str(e),
            )
        t = timeout if timeout is not None else self._timeout
        with self._lock:
            self._ensure_worker()
            code_bytes = code.encode("utf-8")
            self._stdin.write(len(code_bytes).to_bytes(4, "big"))
            self._stdin.write(code_bytes)
            self._stdin.flush()
            result_holder: list = []

            def read_response() -> None:
                try:
                    line = self._stdout.readline()
                    if line:
                        result_holder.append(line)
                except (OSError, ValueError):
                    pass

            reader = threading.Thread(target=read_response, daemon=True)
            reader.start()
            reader.join(timeout=t)
            if reader.is_alive():
                self._process.kill()
                self._process.wait()
                self._process = None
                self._stdin = self._stdout = None
                return RunResult(
                    stdout="",
                    stderr="",
                    success=False,
                    error_message=f"Execution timed out after {t}s.",
                )
            if not result_holder:
                if self._process and self._process.poll() is not None:
                    self._process = None
                    self._stdin = self._stdout = None
                return RunResult(
                    stdout="",
                    stderr="",
                    success=False,
                    error_message="Worker process ended unexpectedly.",
                )
            line = result_holder[0].decode("utf-8", errors="replace").strip()
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                return RunResult(
                    stdout="",
                    stderr=line[:500],
                    success=False,
                    error_message="Invalid response from worker.",
                )
            return RunResult(
                stdout=payload.get("stdout", ""),
                stderr=payload.get("stderr", ""),
                success=payload.get("success", False),
                error_message=payload.get("error_message"),
            )

    def close(self) -> None:
        """Stop the worker process. Safe to call multiple times."""
        with self._lock:
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        self._process.kill()
                    except OSError:
                        pass
                self._process = None
                self._stdin = self._stdout = None

    def __enter__(self) -> "SandboxSession":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
