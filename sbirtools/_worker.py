# Long-lived worker: load award_data once, then run code requests over stdin/stdout.

import json
import sys
from io import StringIO

from sbirtools._sandbox import (
    MAX_CODE_LENGTH,
    MAX_STDOUT_LENGTH,
    _build_sandbox_globals,
    _validate_code_ast,
)
from sbirtools._sandbox import _ForbiddenNodeError


def _run_one(code: str, gl: dict) -> dict:
    """Run code in globals gl; return result dict (stdout, stderr, success, error_message)."""
    out_buf = StringIO()
    err_buf = StringIO()
    try:
        old_stdout, old_stderr = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out_buf, err_buf
        try:
            exec(code, gl)
        finally:
            sys.stdout, sys.stderr = old_stdout, old_stderr
        stdout_str = out_buf.getvalue()
        stderr_str = err_buf.getvalue()
        if len(stdout_str) > MAX_STDOUT_LENGTH:
            stdout_str = stdout_str[:MAX_STDOUT_LENGTH] + "\n... [output truncated]\n"
        return {
            "stdout": stdout_str,
            "stderr": stderr_str,
            "success": True,
            "error_message": None,
        }
    except Exception as e:
        return {
            "stdout": out_buf.getvalue()[:MAX_STDOUT_LENGTH],
            "stderr": err_buf.getvalue(),
            "success": False,
            "error_message": f"{type(e).__name__}: {e}",
        }


def main() -> None:
    """Run worker loop: read length-prefixed code from stdin, run, write JSON line to stdout."""
    gl = _build_sandbox_globals()
    while True:
        try:
            len_buf = sys.stdin.buffer.read(4)
        except (EOFError, OSError):
            break
        if len(len_buf) < 4:
            break
        length = int.from_bytes(len_buf, "big")
        if length <= 0 or length > MAX_CODE_LENGTH:
            result = {
                "stdout": "",
                "stderr": "",
                "success": False,
                "error_message": f"Invalid code length: {length}",
            }
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
            continue
        try:
            code_bytes = sys.stdin.buffer.read(length)
        except (EOFError, OSError):
            break
        if len(code_bytes) < length:
            break
        code = code_bytes.decode("utf-8")
        try:
            _validate_code_ast(code)
        except (_ForbiddenNodeError, ValueError) as e:
            result = {
                "stdout": "",
                "stderr": "",
                "success": False,
                "error_message": str(e),
            }
            sys.stdout.write(json.dumps(result) + "\n")
            sys.stdout.flush()
            continue
        result = _run_one(code, gl)
        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
