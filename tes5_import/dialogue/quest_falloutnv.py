"""FO3/FNV authored quest objectives -> Skyrim QOBJ/FNAM/NNAM/QSTA.

Skyrim kept Fallout's objective layer, so the export's Objective[] blocks are
written as authored: index, text, and each target with its own conditions.
Targets fill the caller's alias table so they become forced-reference aliases
exactly like TES4 targets do.

See: docs/commentary/tes5_import_quest.md#authored-objectives
"""

import struct

from ..base.conditions import convert_ctda_list_with_strings
from ..record_types.common import (
    get_formid,
    get_int,
    get_str,
    pack_string_subrecord,
    pack_subrecord,
    pack_uint32_subrecord,
)


def has_authored_objectives(rec: dict) -> bool:
    """True when the export carries an Objective[] block (FO3/FNV sources)."""
    return 'ObjectiveCount' in rec


def _target_subrecords(rec: dict, pfx: str, alias_by_fid: dict,
                       script_vars: dict, offset: int) -> bytes:
    """QSTA + converted CTDA/CIS2 for every target of one objective."""
    subs = b''
    for t in range(get_int(rec, f'{pfx}.TargetCount')):
        tpfx = f'{pfx}.Target[{t}]'
        tfid = get_formid(rec, f'{tpfx}.FormID')
        if not tfid:
            continue
        alias_id = alias_by_fid.setdefault(tfid, len(alias_by_fid))
        subs += pack_subrecord('QSTA', struct.pack(
            '<iB3x', alias_id, get_int(rec, f'{tpfx}.Flags') & 0x01))
        for ctda, cis2 in convert_ctda_list_with_strings(
                rec, script_vars, offset, prefix=f'{tpfx}.'):
            subs += pack_subrecord('CTDA', ctda)
            if cis2:
                subs += pack_string_subrecord('CIS2', cis2)
    return subs


def authored_objectives(rec: dict, alias_by_fid: dict, script_vars: dict,
                        offset: int) -> bytes:
    """The objective run for a quest whose export carries Objective[] blocks.

    `alias_by_fid` is filled with every target so the caller writes its
    aliases; `script_vars` resolves GetQuestVariable gates to CIS2 names.
    """
    subs = b''
    for i in range(get_int(rec, 'ObjectiveCount')):
        pfx = f'Objective[{i}]'
        subs += pack_subrecord('QOBJ', struct.pack(
            '<H', get_int(rec, f'{pfx}.Index') & 0xFFFF))
        subs += pack_uint32_subrecord('FNAM', 0)
        subs += pack_string_subrecord('NNAM', get_str(rec, f'{pfx}.Text'))
        subs += _target_subrecords(rec, pfx, alias_by_fid, script_vars, offset)
    return subs
