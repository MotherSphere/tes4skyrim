"""TES4 race FormID -> the Oblivion race EditorID that keys RACE_MAP and the face tables.

Oblivion's own races resolve through TES4_RACE_FID_TO_EDID.  A plugin-authored
race has an id no table knows, so it stands in as the known race whose authored
face-part meshes it shares most: Nehrim's Halb-Aeterna wear the same ear mesh
as the Sternling (Oblivion's WoodElf id), so they become Wood Elves.  A race
whose best matches name different races keeps the caller's default.

See: docs/commentary/tes5_import_actors.md#new-races-by-face-parts
"""

from collections import Counter

from .equivalents import TES4_RACE_FID_TO_EDID

#: Plugin-authored race FormID (low 24 bits) -> the known race it stands in as.
_STAND_IN: dict = {}


def tes4_race_edid(race_fid: int, default=None):
    """Known Oblivion race EditorID for a TES4 race FormID, else `default`."""
    fid = (race_fid or 0) & 0x00FFFFFF
    return TES4_RACE_FID_TO_EDID.get(fid) or _STAND_IN.get(fid, default)


def _fid(rec: dict) -> int:
    """Low 24 bits of a record's FormID, 0 when unreadable."""
    try:
        return int((rec.get('FormID') or '0').split()[0], 16) & 0x00FFFFFF
    except ValueError:
        return 0


def _face_parts(rec: dict) -> set:
    """The face-part mesh paths a RACE record authors, normalized."""
    return {v.strip().replace('\\\\', '/').replace('\\', '/').lower()
            for k, v in rec.items()
            if k.startswith('FacePart[') and k.endswith('].Model') and v.strip()}


def _stand_in(parts: set, known: list):
    """The one known EditorID sharing the most face parts with `parts`, or None."""
    shared = Counter()
    for edid, known_parts in known:
        n = len(parts & known_parts)
        shared[edid] = max(shared[edid], n)
    best = max(shared.values(), default=0)
    winners = [e for e, n in shared.items() if n == best]
    return winners[0] if best and len(winners) == 1 else None


def stand_ins(race_records) -> dict:
    """{plugin-authored race FormID (24-bit): the known EditorID it stands in as}."""
    recs = [(_fid(r), r) for r in race_records]
    known = [(TES4_RACE_FID_TO_EDID[fid], _face_parts(r)) for fid, r in recs
             if fid in TES4_RACE_FID_TO_EDID]
    out = {}
    for fid, rec in recs:
        if fid and fid not in TES4_RACE_FID_TO_EDID:
            edid = _stand_in(_face_parts(rec), known)
            if edid:
                out[fid] = edid
    return out


def register_races(race_records) -> int:
    """Register this run's stand-ins for tes4_race_edid; returns how many."""
    _STAND_IN.clear()
    _STAND_IN.update(stand_ins(race_records))
    return len(_STAND_IN)
