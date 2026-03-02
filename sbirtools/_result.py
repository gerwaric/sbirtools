"""RunResult: stdout, stderr, success, error_message. Primary output is stdout."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RunResult:
    """Result of running code in the sandbox. Use stdout as the primary output."""

    stdout: str
    stderr: str
    success: bool
    error_message: Optional[str] = None
