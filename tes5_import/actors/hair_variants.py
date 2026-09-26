"""The hair plan as the import stage reads it: which HDPTs exist and which one an NPC_ wears.

The asset stage bakes a mesh per planned variant; this side emits the matching
HDPTs and points each NPC_ at one.  Both read hair_plan, so they cannot
disagree.  The plan covers the plugin's own hairs and its masters' (whose
variants it only adds where the master's plan lacks them).

See: docs/commentary/asset_convert_armor.md#hair-variants-follow-the-wearer
"""

from asset_convert.character.hair_plan import (RACE_FAMILY, build_plan, hair_entry,
                                               is_own, wearer_variant)
from ..base.text_reader import get_float, get_formid

#: hair FormID (24-bit) -> plan entry, for this run.
_PLAN: dict = {}
#: this run's export folder, as build_plan was given it.
_EXPORT: list = []


def load(export_dir) -> dict:
    """Index this plugin's hair plan (masters included); returns it."""
    _PLAN.clear()
    _EXPORT[:] = [export_dir]
    _PLAN.update(build_plan(export_dir).hairs)
    return _PLAN


def entry(hair_fid: int):
    """The plan entry of a hair FormID (any load-order index), or None."""
    return _PLAN.get((hair_fid or 0) & 0x00FFFFFF)


def entry_for(rec: dict) -> dict:
    """The plan entry of a HAIR record, or a stand-alone one when unplanned."""
    return entry(get_formid(rec, 'FormID')) or hair_entry(rec, None)


def owned_here(e: dict) -> bool:
    """True when this plugin's own HAIR record (not a master's) carries the hair."""
    return bool(_EXPORT) and is_own(e, _EXPORT[0])


def npc_variant(e: dict, rec: dict, race_edid: str, gender: str):
    """The variant an NPC_ record wears: its length, gender and race's head family."""
    return wearer_variant(e, get_float(rec, 'LNAM.HairLength', 0.0),
                          gender == 'Female', RACE_FAMILY.get(race_edid, 'human'))


def master_extras() -> dict:
    """{hair FormID: entry} of master-owned hairs this plugin adds variants to."""
    return {f: e for f, e in _PLAN.items() if e['variants'] and not owned_here(e)}
