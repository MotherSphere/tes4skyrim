"""Rotating per-run log files.

A conversion run's output used to exist only in the GUI's scrollback, so
closing the window -- or starting the next run, which clears the widget --
destroyed the record of the run the user had just played in game.  That is
exactly the evidence that costs a full build-and-play cycle to recreate.

Each run gets its OWN file, named for when it ran and what it ran on::

    logs/run-20260911-143002-Oblivion.esm.log
    logs/run-20260911-101755-Nehrim.esm.log
    logs/run-20260908-224410-global.log      (a run with no plugin selected)

The timestamp leads so a plain lexical sort is newest-last, and the plugin is
in the name so the log for the build the user just played is identifiable
without opening every file.  How many are kept comes from ``logRunsKept`` in
conversion_config.json; a new run PRUNES the surplus oldest rather than
renaming anything, so an existing log's name never changes under a reader.

WHO PRUNES
----------
The run's OWNER prunes, never each process: a GUI pipeline run is usually
several ``convert.py`` invocations (one per step, see gui.py's step loop), so
opening a log per process would leave the retained set holding the last N STEPS
of one run.  The GUI opens one log per run and writes every line through its
own log sink; it sets ``TESCONV_RUN_LOG`` in the child environment, which tells
``convert.py`` a run log already exists so it neither prunes nor writes.  A
bare ``python convert.py`` sees no such variable, so there the process IS the
run and it opens one for itself.

Nothing here may ever fail a conversion.  Every filesystem operation is
individually guarded and degrades to "no logging" rather than raising.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Set by a run owner (the GUI) to the absolute path of the run log it already
# opened.  Its presence means "a run log exists for this run" -- a child must
# not rotate, and must not write.
RUN_LOG_ENV_VAR = "TESCONV_RUN_LOG"

#: Overrides the logs/ directory, so a test never writes beside a live run.
LOGS_DIR_ENV_VAR = "TESCONV_LOGS_DIR"

#: Runs kept when conversion_config.json has no `logRunsKept`.
DEFAULT_RUNS_KEPT = 20

#: Explicit opt-out: `logRunsKept: 0` disables run logging entirely.
MIN_RUNS_KEPT = 0

#: Ceiling on the configured value, so a typo (300 vs 30) cannot hoard gigabytes.
MAX_RUNS_KEPT = 200

#: Stands in for the plugin in a name when a run converts no plugin.
NO_PLUGIN = "global"

_RULE = "-" * 60

_STAMP_FORMAT = "%Y%m%d-%H%M%S"
_NAME_GLOB = "run-*.log"

#: A gap at or above this many seconds is marked, so a slow step is greppable.
SLOW_GAP_SECONDS = 10.0

#: Marks a line whose gap reached SLOW_GAP_SECONDS.
SLOW_MARK = "*"

_ELAPSED_WIDTH = 9

#: Fits "+3600.0" -- a gap longer than an hour is one stage, not a column bug.
_DELTA_WIDTH = 7


def format_stamp(elapsed: float, delta: float) -> str:
    """The `[elapsed +gap]` profiling prefix for one logged line.

    `elapsed` is seconds since the run began, `delta` the gap since the
    previous line; a gap of at least SLOW_GAP_SECONDS carries SLOW_MARK.

    See: docs/commentary/core_run_log.md#profiling-timestamps
    """
    total = max(0.0, elapsed)
    clock = f"{int(total) // 60}:{int(total) % 60:02d}.{int(total * 10) % 10}"
    gap = f"+{max(0.0, delta):.1f}"
    mark = SLOW_MARK if delta >= SLOW_GAP_SECONDS else " "
    return f"[{clock:>{_ELAPSED_WIDTH}} {gap:>{_DELTA_WIDTH}}{mark}] "


def runs_kept(config: dict | None) -> int:
    """How many run logs to keep, from `logRunsKept`, clamped to sane bounds.

    A missing, malformed or out-of-range value falls back to the default
    rather than disabling logging -- a bad config entry should not silently
    cost the user their logs.
    """
    if not config:
        return DEFAULT_RUNS_KEPT
    raw = config.get("logRunsKept", DEFAULT_RUNS_KEPT)
    if isinstance(raw, bool):  # bools are ints; `true` is not a count
        return DEFAULT_RUNS_KEPT
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_RUNS_KEPT
    if n < MIN_RUNS_KEPT or n > MAX_RUNS_KEPT:
        return DEFAULT_RUNS_KEPT
    return n


def logs_root(default) -> Path:
    """Where run logs go: TESCONV_LOGS_DIR if set, else `default`."""
    return Path(os.environ.get(LOGS_DIR_ENV_VAR) or default)


def plugin_label(name: str | None) -> str:
    """`name` reduced to filename-safe characters, or NO_PLUGIN if empty."""
    kept = "".join(c if (c.isalnum() or c in "._- ") else "_"
                   for c in (name or "").strip())
    return kept.strip(" .") or NO_PLUGIN


def log_name(plugin: str | None, when: float | None = None) -> str:
    """Filename for a run on `plugin` started at `when` (default: now)."""
    stamp = time.strftime(_STAMP_FORMAT,
                          time.localtime(time.time() if when is None else when))
    return f"run-{stamp}-{plugin_label(plugin)}.log"


def free_log_path(logs_dir, plugin: str | None) -> Path:
    """An unused log path for a run on `plugin`, now.

    The stamp resolves to the second, and two runs of a fast stage can start
    within one; a suffix keeps the later one from overwriting the earlier.
    """
    logs = Path(logs_dir)
    base = log_name(plugin)
    path = logs / base
    for n in range(2, 100):
        if not path.exists():
            return path
        path = logs / f"{base[:-len('.log')]}-{n}.log"
    return path


def _sort_key(path: Path):
    """Chronological key for a run log: its name, then mtime as a tiebreak."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        mtime = 0.0
    return (path.name, mtime)


def existing_logs(logs_dir) -> list[Path]:
    """Every run log present, NEWEST FIRST.  Never raises.

    Ordered by name, which the leading timestamp makes chronological, with
    mtime as the tiebreak for hand-renamed files.
    """
    try:
        return sorted(Path(logs_dir).glob(_NAME_GLOB), key=_sort_key,
                      reverse=True)
    except OSError:
        return []


def latest_log(logs_dir) -> Path | None:
    """The most recent run log, or None when none exist."""
    logs = existing_logs(logs_dir)
    return logs[0] if logs else None


def prune(logs_dir, keep: int = DEFAULT_RUNS_KEPT) -> bool:
    """Delete all but the `keep - 1` newest logs, making room for a new one.

    `keep - 1` because the caller is about to add one; pruning to `keep` would
    leave `keep + 1` on disk.  Deleting rather than renaming means an existing
    log's name never changes, so a path the user opened stays valid.  A file
    locked by an editor is skipped, the rest still pruned.

    Returns True if a new log may be opened.  Never raises.
    """
    if keep <= 0:
        return False
    try:
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    for path in existing_logs(logs_dir)[max(0, keep - 1):]:
        try:
            path.unlink()
        except OSError:
            pass
    return True


class RunLog:
    """A single run's log file: header, verbatim lines, footer.

    Line-buffered and flushed per line -- a log that only reaches disk on
    clean exit is empty exactly when it matters most (a crash or a hang).  The
    cost is nothing next to a stage that saturates every core for minutes.
    """

    def __init__(self, path, header: dict | None = None):
        self.path = Path(path)
        self._fh = None
        self._start = time.time()
        self._last = self._start
        try:
            self._fh = open(self.path, "w", encoding="utf-8",
                            errors="replace", newline="\n")
        except OSError:
            self._fh = None
            return
        self._write_header(header or {})

    @property
    def active(self) -> bool:
        return self._fh is not None

    def _raw(self, text: str):
        if self._fh is None:
            return
        try:
            self._fh.write(text)
            self._fh.flush()
        except (OSError, ValueError):
            # The disk filled, or the handle died.  Stop trying; a conversion
            # must never fail because its log could not be written.
            try:
                self._fh.close()
            except (OSError, ValueError):
                pass
            self._fh = None

    def _write_header(self, header: dict):
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._start))
        lines = ["# TESRACT run log", f"# Started:  {stamp}"]
        for key, value in header.items():
            if value in (None, ""):
                continue
            lines.append(f"# {key + ':':9} {value}")
        lines.append(f"# {'Columns:':9} [elapsed +gap] -- "
                     f"{SLOW_MARK} marks a gap over {SLOW_GAP_SECONDS:.0f}s")
        lines.append(_RULE)
        self._raw("\n".join(lines) + "\n")

    def write_line(self, line: str):
        """Append one line, prefixed with its elapsed/gap profiling stamp.

        The text is otherwise verbatim -- tags are presentation, and only the
        stamp is added, so the log stays a faithful record of the run's output.
        """
        now = time.time()
        stamp = format_stamp(now - self._start, now - self._last)
        self._last = now
        self._raw(stamp + line.rstrip("\r\n") + "\n")

    def close(self, status: str | None = None):
        """Write the footer and close.

        A run killed mid-flight simply has no footer, which is itself the
        signal that it did not terminate cleanly.
        """
        if self._fh is None:
            return
        elapsed = time.time() - self._start
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        tail = f"# Finished: {stamp}  ({format_elapsed(elapsed)})"
        if status:
            tail += f"  {status}"
        self._raw(_RULE + "\n" + tail + "\n")
        try:
            self._fh.close()
        except (OSError, ValueError):
            pass
        self._fh = None

    # Context-manager sugar so a CLI run closes on any exit path.
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close("EXIT: OK" if exc_type is None else f"EXIT: {exc_type.__name__}")
        return False


def format_elapsed(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def format_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


class Tee:
    """Mirror a text stream into a RunLog, line by line.

    Wraps sys.stdout/sys.stderr for the CLI path, where there is no GUI sink
    to hook.  Partial writes are buffered until a newline so a progress line
    built from several `print(..., end="")` calls lands as one log line.
    """

    def __init__(self, stream, run_log: RunLog):
        self._stream = stream
        self._log = run_log
        self._buf = ""

    def write(self, text):
        try:
            n = self._stream.write(text)
        except (OSError, ValueError):
            n = len(text)
        if self._log is not None and text:
            self._buf += text
            if "\n" in self._buf:
                *lines, self._buf = self._buf.split("\n")
                for line in lines:
                    self._log.write_line(line)
        return n

    def flush(self):
        try:
            self._stream.flush()
        except (OSError, ValueError):
            pass

    def close_buffer(self):
        """Flush a trailing partial line (no newline) into the log."""
        if self._log is not None and self._buf:
            self._log.write_line(self._buf)
            self._buf = ""

    # Anything else -- isatty, encoding, fileno, buffer -- passes through, so
    # the wrapper stays transparent to code that inspects the stream.
    def __getattr__(self, name):
        return getattr(self._stream, name)


def plugin_from_argv(argv=None) -> str | None:
    """The plugin `-f`/`--file` names in `argv`, or None when it names none."""
    args = list(sys.argv[1:] if argv is None else argv)
    for i, arg in enumerate(args):
        if arg in ("-f", "--file") and i + 1 < len(args):
            return args[i + 1]
        for prefix in ("--file=", "-f="):
            if arg.startswith(prefix):
                return arg.split("=", 1)[1]
    return None


def start_cli_run(logs_dir, config: dict | None, header: dict | None = None):
    """Prune and begin a run log for a standalone CLI run, teeing stdout.

    The log is named for the plugin `-f` selects, read from argv here so the
    caller needs no second copy of that parsing.

    Returns the RunLog, or None when logging is disabled (`logRunsKept: 0`),
    unavailable, or when a run owner already opened one (the GUI case, flagged
    by TESCONV_RUN_LOG).  Callers must pair a non-None result with `finish`.
    """
    if os.environ.get(RUN_LOG_ENV_VAR):
        return None  # a parent owns this run's log
    keep = runs_kept(config)
    if keep <= 0:
        return None
    logs_dir = logs_root(logs_dir)
    if not prune(logs_dir, keep):
        return None
    run_log = RunLog(free_log_path(logs_dir, plugin_from_argv()), header)
    if not run_log.active:
        return None
    sys.stdout = Tee(sys.stdout, run_log)
    sys.stderr = Tee(sys.stderr, run_log)
    return run_log


def finish_cli_run(run_log, status: str | None = None):
    """Unwrap the teed streams and close the run log.  Never raises."""
    if run_log is None:
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if isinstance(stream, Tee):
            stream.close_buffer()
            setattr(sys, name, stream._stream)
    run_log.close(status)
