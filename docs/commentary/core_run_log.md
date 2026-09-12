# Run logs

**Code:** `core/run_log.py`, `core/gui/runner.py`

Each conversion run writes one file under `logs/`, named for when it ran and
what it ran on. `core/run_log.py` documents the naming, retention and
degradation contracts in its own module docstring; this file covers the parts
whose REASONING does not belong in a docstring.

## Profiling timestamps

Every logged line carries a prefix:

```
[      0:00  +0.0 ] ======================================================
[     0:12.6 +12.6*]   Parsed 1167016 records in 63 types (12.66s)
[     0:12.7  +0.1 ]   Phase: parse export text (12.7s)
```

The columns are **elapsed since the run started** and **the gap since the
previous line**, and a gap of at least `SLOW_GAP_SECONDS` (10s) is marked with
`*`.

### Why the gap column exists

Elapsed alone does not answer the profiling question. A stage's cost is the
SILENCE BEFORE the line that announces it finished, so reading elapsed means
subtracting every pair of adjacent lines by hand -- over a 15-minute run of
250+ lines, across several stages. The gap column does that subtraction once,
at write time, and the `*` mark makes the expensive steps greppable:

```bash
grep '\*\]' logs/run-20260911-203028-Oblivion.esm.log     # every slow step
```

This is deliberately NOT a substitute for the `Phase:` lines the import stage
already prints. Those measure a stage from the inside and are authoritative;
the gap column covers everything BETWEEN them, which is where an unattributed
minute hides. The two disagreeing is itself informative -- it means time went
somewhere no phase timer was watching.

### Why elapsed, not wall clock

The header already records `# Started:` as an absolute local time, so wall
clock is recoverable by addition, while elapsed is not recoverable from wall
clock without reading the header every time. Elapsed also makes two runs of
the same plugin directly comparable line-for-line, which is the whole point of
keeping the last N runs.

### Why it is stamped in `RunLog.write_line`

Both writers converge there -- the CLI's `Tee` over stdout/stderr, and the
GUI's sink in `core/gui/runner.py`, which owns the log for a multi-process
pipeline run. Stamping at that single point means:

- every line is stamped regardless of which path produced it, including the
  GUI's own header and error-summary lines, which are in no child's stdout;
- the timestamps are the LOG's, not the child processes' -- a GUI pipeline run
  is several `convert.py` invocations, and per-process elapsed would restart
  at zero on each step, making the run unprofilable exactly where it is
  slowest;
- the terminal and GUI scrollback stay unstamped. The prefix is for reading
  the file afterwards; live output is already time-ordered on screen.

### Continuation lines

A line the GUI indents as a continuation of a progress block still gets its
own stamp. That is intentional: a progress line printed every 10% of a
download is exactly the signal that shows where a transfer stalled.
