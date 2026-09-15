"""FO3/FNV QUST fields the TES4 walker cannot see: the delay and the objectives.

The 8-byte DATA carries a Quest Delay float after TES4's two bytes, and the
targets sit inside QOBJ/NNAM objectives instead of a flat list.  Pure dump:
every value is emitted as authored.

See: docs/commentary/tes4_export_falloutnv.md#quest-delay-and-objectives
"""

import struct

from ..tes4_reader import Record, get_formid_str, get_string, get_subrecord
from .common import escape_value

#: KEY= prefixes of the TES4 walker's flat target list, superseded by Objective[].
SUPERSEDED_QUEST_KEYS = ("TargetCount=", "Target[")

#: DATA length that carries the Quest Delay float at offset 4.
_DATA_WITH_DELAY = 8


def _add_objective_subrecord(objectives: list, sub) -> None:
    """Attach one subrecord to the objective it belongs to, by POSITION.

    Each objective is [index, text, [(target fid, flags, [raw ctda])]]; a
    CTDA guards the QSTA it follows.
    """
    if sub.type == "QOBJ" and len(sub.data) >= 4:
        objectives.append([struct.unpack_from("<i", sub.data, 0)[0], "", []])
        return
    if not objectives:
        return
    current = objectives[-1]
    if sub.type == "NNAM":
        current[1] = get_string(sub)
    if sub.type == "QSTA" and len(sub.data) >= 5:
        current[2].append(
            (struct.unpack_from("<I", sub.data, 0)[0], sub.data[4], []))
    if sub.type == "CTDA" and current[2]:
        current[2][-1][2].append(sub.data)


def _emit_targets(lines: list, pfx: str, targets: list) -> None:
    """The Target[j] block under one objective, conditions included."""
    lines.append(f"{pfx}.TargetCount={len(targets)}")
    for j, (fid, flags, ctdas) in enumerate(targets):
        tpfx = f"{pfx}.Target[{j}]"
        lines.append(f"{tpfx}.FormID={get_formid_str(fid)}")
        lines.append(f"{tpfx}.Flags={flags}")
        if ctdas:
            lines.append(f"{tpfx}.ConditionCount={len(ctdas)}")
            for k, raw in enumerate(ctdas):
                lines.append(f"{tpfx}.Condition[{k}].Raw={raw.hex()}")


def emit_quest_deltas(lines: list, rec: Record) -> None:
    """Append DATA.Delay and the Objective[] blocks of one FO3/FNV QUST."""
    data = get_subrecord(rec, "DATA")
    if data and len(data.data) >= _DATA_WITH_DELAY:
        lines.append(f"DATA.Delay={struct.unpack_from('<f', data.data, 4)[0]:g}")
    objectives = []
    for sub in rec.subrecords:
        _add_objective_subrecord(objectives, sub)
    if not objectives:
        return
    lines.append(f"ObjectiveCount={len(objectives)}")
    for i, (index, text, targets) in enumerate(objectives):
        pfx = f"Objective[{i}]"
        lines.append(f"{pfx}.Index={index}")
        lines.append(f"{pfx}.Text={escape_value(text)}")
        _emit_targets(lines, pfx, targets)
