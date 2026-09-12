"""Tests for run_log: naming, retention, config clamping, degradation."""

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.run_log as run_log

_WHEN = time.mktime((2026, 9, 11, 14, 30, 2, 0, 0, -1))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(logs, name, text):
    """Create one file under `logs` with the given name and contents."""
    (Path(logs) / name).write_text(text, encoding="utf-8")


def _run(logs, stamp, plugin="Oblivion.esm", text="x"):
    """Create a log as a run at `stamp` would have; returns its name."""
    name = f"run-{stamp}-{plugin}.log"
    _write(logs, name, text)
    return name


def _names(logs):
    """Every run-log name under `logs`, oldest first."""
    return sorted(p.name for p in Path(logs).glob("run-*.log"))


def _path(logs):
    """A run-log path under `logs` for tests about file contents, not naming."""
    return Path(logs) / run_log.log_name("Oblivion.esm")


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------

def test_log_name_carries_stamp_and_plugin():
    """The name states when the run happened and what it converted."""
    assert run_log.log_name("Oblivion.esm", _WHEN) == \
        "run-20260911-143002-Oblivion.esm.log"


def test_log_name_without_plugin_uses_placeholder():
    """A global action still gets a name, with NO_PLUGIN standing in."""
    assert run_log.log_name(None, _WHEN) == \
        f"run-20260911-143002-{run_log.NO_PLUGIN}.log"


@pytest.mark.parametrize("raw,expected", [
    ("Oblivion.esm", "Oblivion.esm"),
    ("Tamriel Landscape Pack", "Tamriel Landscape Pack"),
    ("a/b\\c:d*e?f", "a_b_c_d_e_f"),
    ("", run_log.NO_PLUGIN),
    (None, run_log.NO_PLUGIN),
    ("   ", run_log.NO_PLUGIN),
    ("...", run_log.NO_PLUGIN),
])
def test_plugin_label(raw, expected):
    """Path and glob characters are neutralised; nothing yields a dotfile."""
    assert run_log.plugin_label(raw) == expected


def test_free_log_path_never_overwrites_the_same_second(tmp_path):
    """Two fast runs inside one second must not collapse into one file."""
    first = run_log.free_log_path(tmp_path, "Oblivion.esm")
    first.write_text("first", encoding="utf-8")
    second = run_log.free_log_path(tmp_path, "Oblivion.esm")
    assert second != first
    second.write_text("second", encoding="utf-8")
    assert first.read_text(encoding="utf-8") == "first"


def test_free_log_path_is_plain_when_the_second_is_free(tmp_path):
    """The suffix appears only on a collision, never on a normal run."""
    assert run_log.free_log_path(tmp_path, "Oblivion.esm").name == \
        run_log.log_name("Oblivion.esm")


def test_log_name_is_openable_for_a_hostile_plugin(tmp_path):
    """A mod title with a colon and a slash must still open."""
    path = tmp_path / run_log.log_name("Mod: v2/beta")
    run_log.RunLog(path, {}).close()
    assert path.exists()


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_existing_logs_is_newest_first(tmp_path):
    """Listing order is chronological regardless of creation order."""
    _run(tmp_path, "20260901-120000")
    _run(tmp_path, "20260911-090000")
    _run(tmp_path, "20260905-235959")
    assert [p.name.split("-")[1] for p in run_log.existing_logs(tmp_path)] == \
        ["20260911", "20260905", "20260901"]


def test_latest_log_picks_the_newest_whatever_the_plugin(tmp_path):
    """Recency wins: the plugin name must not influence the ordering."""
    _run(tmp_path, "20260911-090000", "Zzz.esm")
    newest = _run(tmp_path, "20260911-100000", "Aaa.esm")
    assert run_log.latest_log(tmp_path).name == newest


def test_latest_log_when_empty(tmp_path):
    """No logs yet is None, not a crash."""
    assert run_log.latest_log(tmp_path) is None


def test_existing_logs_ignores_foreign_files(tmp_path):
    """Only run logs count -- logs/ holds other files too."""
    _write(tmp_path, "notes.txt", "x")
    _write(tmp_path, "compile_errors.log", "x")
    kept = _run(tmp_path, "20260911-090000")
    assert [p.name for p in run_log.existing_logs(tmp_path)] == [kept]


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

def test_prune_leaves_room_for_the_new_run(tmp_path):
    """keep=3 means 3 on disk AFTER the run, so 2 survive the prune."""
    for day in range(1, 4):
        _run(tmp_path, f"202609{day:02d}-120000")
    assert run_log.prune(tmp_path, keep=3) is True
    assert _names(tmp_path) == ["run-20260902-120000-Oblivion.esm.log",
                                "run-20260903-120000-Oblivion.esm.log"]


def test_prune_evicts_only_the_oldest(tmp_path):
    """Twenty-five runs at keep=20: the retained set is the newest 20."""
    for day in range(1, 26):
        run_log.prune(tmp_path, keep=20)
        _run(tmp_path, f"202609{day:02d}-120000")
        assert len(_names(tmp_path)) == min(day, 20)
    kept = _names(tmp_path)
    assert kept[0] == "run-20260906-120000-Oblivion.esm.log"
    assert kept[-1] == "run-20260925-120000-Oblivion.esm.log"


def test_prune_keeps_names_stable(tmp_path):
    """A surviving log keeps its name -- a reader's path stays valid."""
    survivor = _run(tmp_path, "20260911-120000", text="survivor")
    _run(tmp_path, "20260901-120000", text="evicted")
    run_log.prune(tmp_path, keep=2)
    assert (tmp_path / survivor).read_text(encoding="utf-8") == "survivor"


def test_prune_when_keep_lowered(tmp_path):
    """Lowering logRunsKept prunes the surplus instead of orphaning it."""
    for day in range(1, 6):
        _run(tmp_path, f"202609{day:02d}-120000")
    run_log.prune(tmp_path, keep=2)
    assert _names(tmp_path) == ["run-20260905-120000-Oblivion.esm.log"]


def test_prune_creates_missing_dir(tmp_path):
    """The first ever run creates logs/."""
    logs = tmp_path / "logs"
    assert run_log.prune(logs, keep=3) is True
    assert logs.is_dir()


def test_prune_disabled_when_keep_zero(tmp_path):
    """The opt-out declines the run; it must never delete what is there."""
    kept = _run(tmp_path, "20260911-120000")
    assert run_log.prune(tmp_path, keep=0) is False
    assert _names(tmp_path) == [kept]


def test_prune_of_empty_dir(tmp_path):
    """Nothing to prune still authorises the new log."""
    assert run_log.prune(tmp_path, keep=3) is True


# ---------------------------------------------------------------------------
# Plugin from argv
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argv,expected", [
    (["-f", "Oblivion.esm", "--export-only"], "Oblivion.esm"),
    (["--file", "Nehrim.esm"], "Nehrim.esm"),
    (["--file=Nehrim.esm"], "Nehrim.esm"),
    (["-f=Nehrim.esm"], "Nehrim.esm"),
    (["--meshes-only"], None),
    (["-f"], None),
    ([], None),
])
def test_plugin_from_argv(argv, expected):
    """A dangling -f with no value names no plugin rather than crashing."""
    assert run_log.plugin_from_argv(argv) == expected


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT = run_log.DEFAULT_RUNS_KEPT


@pytest.mark.parametrize("cfg,expected", [
    (None, _DEFAULT),
    ({}, _DEFAULT),
    ({"logRunsKept": 5}, 5),
    ({"logRunsKept": 0}, 0),               # explicit opt-out is honoured
    ({"logRunsKept": "7"}, 7),             # JSON string coerces
    ({"logRunsKept": 200}, 200),           # the ceiling itself is allowed
    ({"logRunsKept": -1}, _DEFAULT),       # out of range -> default
    ({"logRunsKept": 5000}, _DEFAULT),     # absurd -> default, never hoard
    ({"logRunsKept": "abc"}, _DEFAULT),    # malformed -> default
    ({"logRunsKept": None}, _DEFAULT),
    ({"logRunsKept": True}, _DEFAULT),     # bool is not a count
])
def test_runs_kept(cfg, expected):
    """A bad value falls back rather than costing the user their logs."""
    assert run_log.runs_kept(cfg) == expected


# ---------------------------------------------------------------------------
# File contents
# ---------------------------------------------------------------------------

def test_header_footer_roundtrip(tmp_path):
    path = _path(tmp_path)
    log = run_log.RunLog(path, {"Command": "Pipeline run", "Steps": "export"})
    log.write_line("hello")
    log.write_line("world")
    log.close("EXIT: OK")

    text = path.read_text(encoding="utf-8")
    assert "# TESRACT run log" in text
    assert "# Started:" in text
    assert "Command:  Pipeline run" in text
    assert "Steps:    export" in text
    assert "] hello\n" in text and "] world\n" in text
    assert "# Finished:" in text and "EXIT: OK" in text


def test_lines_written_before_close(tmp_path):
    """A hung or killed run must still have its lines on disk."""
    path = _path(tmp_path)
    log = run_log.RunLog(path, {})
    log.write_line("partial progress")
    # Deliberately not closed -- simulates a kill.
    assert "partial progress" in path.read_text(encoding="utf-8")
    assert "# Finished:" not in path.read_text(encoding="utf-8")
    log.close()


def test_empty_header_values_skipped(tmp_path):
    path = _path(tmp_path)
    run_log.RunLog(path, {"Command": "x", "Output": "", "Version": None}).close()
    text = path.read_text(encoding="utf-8")
    assert "Output" not in text and "Version" not in text


def test_write_after_failure_is_silent(tmp_path):
    """A dead handle degrades to no-op; it must never raise into a run."""
    log = run_log.RunLog(_path(tmp_path), {})
    log._fh.close()          # simulate the handle dying mid-run
    log.write_line("still fine")   # must not raise
    log.close()
    assert log.active is False


def test_unwritable_path_degrades(tmp_path):
    """An undeletable/unopenable target yields an inactive log, not a crash."""
    target = tmp_path / "run-1.log"
    target.mkdir()           # a directory cannot be opened for writing
    log = run_log.RunLog(target, {})
    assert log.active is False
    log.write_line("ignored")
    log.close("EXIT: OK")


# ---------------------------------------------------------------------------
# Tee
# ---------------------------------------------------------------------------

class _FakeStream:
    def __init__(self):
        self.text = ""

    def write(self, s):
        self.text += s
        return len(s)

    def flush(self):
        pass


def test_tee_mirrors_and_passes_through(tmp_path):
    path = _path(tmp_path)
    log = run_log.RunLog(path, {})
    stream = _FakeStream()
    tee = run_log.Tee(stream, log)

    tee.write("alpha\nbeta\n")
    assert stream.text == "alpha\nbeta\n"      # console unaffected
    body = path.read_text(encoding="utf-8")
    assert "alpha" in body and "beta" in body
    log.close()


def test_tee_buffers_partial_lines(tmp_path):
    """print(..., end="") fragments must land as ONE log line."""
    path = _path(tmp_path)
    log = run_log.RunLog(path, {})
    tee = run_log.Tee(_FakeStream(), log)

    tee.write("Converting ")
    tee.write("mesh 5/10")
    assert "Converting" not in path.read_text(encoding="utf-8")  # still buffered
    tee.write("\n")
    assert "Converting mesh 5/10" in path.read_text(encoding="utf-8")
    log.close()


def test_tee_flushes_trailing_partial_on_finish(tmp_path):
    path = _path(tmp_path)
    log = run_log.RunLog(path, {})
    real_out = sys.stdout
    sys.stdout = run_log.Tee(_FakeStream(), log)
    sys.stdout.write("no trailing newline")
    try:
        run_log.finish_cli_run(log, "EXIT: OK")
    finally:
        sys.stdout = real_out
    assert "no trailing newline" in path.read_text(encoding="utf-8")


def test_tee_forwards_unknown_attributes():
    stream = _FakeStream()
    stream.encoding = "utf-8"
    assert run_log.Tee(stream, None).encoding == "utf-8"


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

def test_child_process_does_not_open_its_own_log(tmp_path, monkeypatch):
    """TESCONV_RUN_LOG set => a parent owns the run; the child must not write."""
    monkeypatch.setenv(run_log.RUN_LOG_ENV_VAR, str(tmp_path / "run-1.log"))
    assert run_log.start_cli_run(tmp_path, {"logRunsKept": 3}) is None
    assert list(tmp_path.glob("run-*.log")) == []


def test_start_cli_run_opens_and_tees(tmp_path, monkeypatch):
    """The new log is named from argv's -f, and the prior run survives."""
    monkeypatch.delenv(run_log.RUN_LOG_ENV_VAR, raising=False)
    monkeypatch.setattr(sys, "argv", ["convert.py", "-f", "Nehrim.esm"])
    previous = _run(tmp_path, "20260101-120000", text="previous run")
    real_out, real_err = sys.stdout, sys.stderr
    try:
        log = run_log.start_cli_run(tmp_path, {"logRunsKept": 3},
                                    {"Command": "convert.py"})
        assert log is not None
        assert isinstance(sys.stdout, run_log.Tee)
        print("captured line")
        run_log.finish_cli_run(log, "EXIT: OK")
    finally:
        sys.stdout, sys.stderr = real_out, real_err

    assert sys.stdout is real_out                     # streams restored
    assert log.path.name.endswith("-Nehrim.esm.log")
    assert (tmp_path / previous).read_text(encoding="utf-8") == "previous run"
    assert "captured line" in log.path.read_text(encoding="utf-8")


def test_start_cli_run_names_a_pluginless_run(tmp_path, monkeypatch):
    """A global run (no -f in argv) still gets a log."""
    monkeypatch.delenv(run_log.RUN_LOG_ENV_VAR, raising=False)
    monkeypatch.setattr(sys, "argv", ["convert.py", "--lod-only"])
    real_out, real_err = sys.stdout, sys.stderr
    try:
        log = run_log.start_cli_run(tmp_path, {"logRunsKept": 3})
        run_log.finish_cli_run(log, "EXIT: OK")
    finally:
        sys.stdout, sys.stderr = real_out, real_err
    assert log.path.name.endswith(f"-{run_log.NO_PLUGIN}.log")


def test_start_cli_run_disabled_returns_none(tmp_path, monkeypatch):
    """`logRunsKept: 0` opts out without teeing the streams."""
    monkeypatch.delenv(run_log.RUN_LOG_ENV_VAR, raising=False)
    assert run_log.start_cli_run(tmp_path, {"logRunsKept": 0}) is None
    assert not isinstance(sys.stdout, run_log.Tee)


def test_finish_cli_run_accepts_none():
    run_log.finish_cli_run(None)  # must not raise


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("secs,expected", [
    (0, "0s"), (9, "9s"), (61, "1m 01s"), (3600, "1h 00m 00s"),
    (3661, "1h 01m 01s"), (-5, "0s"),
])
def test_format_elapsed(secs, expected):
    assert run_log.format_elapsed(secs) == expected


@pytest.mark.parametrize("elapsed,delta,expected", [
    (0.0, 0.0, "[   0:00.0    +0.0 ] "),
    (12.66, 12.62, "[   0:12.6   +12.6*] "),
    (60.0, 0.1, "[   1:00.0    +0.1 ] "),
    (3601.2, 0.3, "[  60:01.2    +0.3 ] "),
    (-1.0, -1.0, "[   0:00.0    +0.0 ] "),
])
def test_format_stamp(elapsed, delta, expected):
    """The prefix renders as `[elapsed +gap]`, clamping negatives to zero."""
    assert run_log.format_stamp(elapsed, delta) == expected


def test_format_stamp_columns_align():
    """Every stamp is the same width, or the log's columns do not line up."""
    widths = {len(run_log.format_stamp(e, d))
              for e, d in [(0, 0), (9.9, 9.9), (599.5, 539.5), (7200, 3600),
                           (86400, 7200)]}
    assert len(widths) == 1


def test_slow_gap_marked_at_threshold():
    """The mark is what makes slow steps greppable, so the boundary matters."""
    assert run_log.SLOW_MARK in run_log.format_stamp(99, run_log.SLOW_GAP_SECONDS)
    assert run_log.SLOW_MARK not in \
        run_log.format_stamp(99, run_log.SLOW_GAP_SECONDS - 0.1)


def test_write_line_stamps_each_line_and_keeps_text(tmp_path):
    """Stamps are added; the line's own text is otherwise untouched."""
    path = _path(tmp_path)
    log = run_log.RunLog(path, {})
    log.write_line("  ACHR: 2190 records [CONVERT]")
    log.close()
    body = [ln for ln in path.read_text(encoding="utf-8").splitlines()
            if "ACHR" in ln]
    assert len(body) == 1
    assert body[0].endswith("  ACHR: 2190 records [CONVERT]")
    assert body[0].startswith("[")


def test_gap_measures_since_previous_line(monkeypatch):
    """The gap is line-to-line, not since the run began -- that is the point."""
    clock = [1000.0]
    monkeypatch.setattr(run_log.time, "time", lambda: clock[0])
    stamps = []
    monkeypatch.setattr(run_log.RunLog, "_raw",
                        lambda self, text: stamps.append(text))
    log = run_log.RunLog.__new__(run_log.RunLog)
    log._fh, log._start, log._last = object(), clock[0], clock[0]
    for advance in (5.0, 2.0):
        clock[0] += advance
        log.write_line("x")
    assert "+5.0" in stamps[0] and "+2.0" in stamps[1]
    assert "0:05" in stamps[0] and "0:07" in stamps[1]


def test_format_size():
    assert run_log.format_size(512) == "512 B"
    assert run_log.format_size(2048) == "2.0 KB"
    assert run_log.format_size(5 * 1024 * 1024) == "5.0 MB"
