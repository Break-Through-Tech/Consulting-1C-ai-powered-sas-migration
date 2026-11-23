"""
Protections for the shared Gemini key: access code, upload limits and rate limits.

The key itself never reaches the browser: it's read from Streamlit secrets on
the server and only used for the server's own calls to Gemini.
"""
from __future__ import annotations

import hmac
import threading
import time
from dataclasses import dataclass, field
from datetime import date

MAX_FILES = 10
MAX_FILE_BYTES = 200_000       # per .sas file
MAX_TOTAL_BYTES = 500_000      # per translation request
MAX_CODE_ATTEMPTS = 5          # wrong access codes before a lockout
LOCKOUT_SECONDS = 600
RUNS_PER_HOUR = 5              # translations per browser session per hour
DEFAULT_DAILY_LIMIT = 50       # translations per day across all visitors


def code_matches(entered: str, expected: str) -> bool:
    """Constant-time comparison, so response timing doesn't leak the code."""
    if not expected:
        return False
    return hmac.compare_digest(entered.strip().encode(), expected.strip().encode())


def decode_sas(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def check_uploads(files: list[tuple[str, bytes]]) -> list[str]:
    """Problems with an upload batch (empty list = OK)."""
    problems = []
    if not files:
        problems.append("Add at least one .sas file.")
    if len(files) > MAX_FILES:
        problems.append(f"At most {MAX_FILES} files per translation (got {len(files)}).")
    total = 0
    for name, data in files:
        total += len(data)
        if not name.lower().endswith(".sas"):
            problems.append(f"{name}: only .sas files are accepted.")
        if len(data) > MAX_FILE_BYTES:
            problems.append(f"{name}: {len(data):,} bytes is over the {MAX_FILE_BYTES:,}-byte limit per file.")
        if not data.strip():
            problems.append(f"{name}: the file is empty.")
    if total > MAX_TOTAL_BYTES:
        problems.append(f"The files total {total:,} bytes, over the {MAX_TOTAL_BYTES:,}-byte limit.")
    return problems


@dataclass
class SessionGuard:
    """Per-browser-session state: failed codes and recent translations."""
    failed_codes: int = 0
    locked_until: float = 0.0
    run_times: list[float] = field(default_factory=list)

    def locked(self, now: float | None = None) -> float:
        """Seconds left in a lockout (0 if not locked)."""
        return max(0.0, self.locked_until - (time.time() if now is None else now))

    def record_failed_code(self, now: float | None = None) -> None:
        self.failed_codes += 1
        if self.failed_codes >= MAX_CODE_ATTEMPTS:
            self.locked_until = (time.time() if now is None else now) + LOCKOUT_SECONDS
            self.failed_codes = 0

    def runs_left(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        self.run_times = [t for t in self.run_times if now - t < 3600]
        return max(0, RUNS_PER_HOUR - len(self.run_times))

    def record_run(self, now: float | None = None) -> None:
        self.run_times.append(time.time() if now is None else now)


class DailyLimit:
    """Translations per day across every visitor (shared by the whole app process)."""

    def __init__(self, limit: int = DEFAULT_DAILY_LIMIT):
        self.limit = limit
        self._day = date.today()
        self._count = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        if date.today() != self._day:
            self._day, self._count = date.today(), 0

    def remaining(self) -> int:
        with self._lock:
            self._roll()
            return max(0, self.limit - self._count)

    def take(self) -> bool:
        """Use one translation from today's allowance; False if none are left."""
        with self._lock:
            self._roll()
            if self._count >= self.limit:
                return False
            self._count += 1
            return True
