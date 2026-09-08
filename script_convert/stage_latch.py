"""The stage-arrival latch on `GetStage()==N && <timer> <= 0` guards.

The timer such a guard waits on is charged by stage N's OWN fragment, and
nothing makes that charge land before the guard is first tested -- so the guard
fires on the frame stage N arrives, before the fragment has said anything.

See: docs/commentary/script_convert.md#stage-arrival-latch
"""

import re

#: `<quest>.GetStage() == N` and `<timer> <= 0` in ONE condition, either order.
STAGE_TIMER_GUARD_RE = re.compile(
    r'^(?P<indent>\s*)If\s+(?P<cond>.*?\b(?P<q>[A-Za-z_]\w*)\.GetStage\(\)\s*=='
    r'\s*(?P<stage>\d+)\b.*?)\s*$', re.IGNORECASE)

#: The `<timer> <= 0` half, which may sit anywhere in the same condition.
TIMER_ZERO_RE = re.compile(
    r'\b(?P<timer>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)?)\s*<=\s*0(?:\.0*)?\b')


def latch_var(conv, quest: str) -> str:
    """The "stage we saw last pass" latch for `quest`, registered for emission.

    Keyed case-insensitively; see the module's doc section for why.
    """
    key = quest.lower()
    var = conv.sc.stage_latches.get(key)
    if var is None:
        var = f'TES4_LastStage_{quest}'
        conv.sc.stage_latches[key] = var
    return var


def guard_stage_timer(conv, line: str) -> str:
    """Add the stage-arrival latch to a `GetStage()==N && <timer> <= 0` guard.

    Requires one full poll pass at stage N before the guard is honoured, which
    is what lets stage N's fragment run and charge the timer.
    """
    if 'GetStage()' not in line or '<=' not in line:
        return line
    m = STAGE_TIMER_GUARD_RE.match(line)
    if not m or not TIMER_ZERO_RE.search(m.group('cond')):
        return line
    stage = m.group('stage')
    var = latch_var(conv, m.group('q'))
    return (f'{m.group("indent")}If {m.group("cond")} && {var} == {stage}'
            f'  ; stage-arrival latch: stage {stage} seen a full pass, '
            f'so its fragment has run')
