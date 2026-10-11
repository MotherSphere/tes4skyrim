"""Morrowind NPC animation files played through vanilla furniture and idle markers.

An NPC that names its own animation file (`MorrowindAnim`) sits, lies, kneels
or works through that file's idles. Most have a vanilla counterpart the engine
plays itself: each placement of such an NPC gets the marker as a new
reference at its authored spot, linked from the actor (XLKR), and the NPC's
wander package becomes SitTarget or UseIdleMarker on that linked reference.
See: docs/commentary/asset_convert_animation.md#vanilla-markers-for-npc-animation-files
"""

import math
import struct

from ..base.text_reader import get_formid, get_int
from ..packages.converter import MARKER_IDLE, MARKER_KEY, MARKER_SIT
from .common import pack_record, pack_string_subrecord, pack_subrecord

#: derive_formid sites: a marker per placement (keyed by its ACHR), an idle marker per EditorID.
_REF_SITE = 'MW_NPC_MARKER'
_IDLM_SITE = 'MW_IDLE_MARKER'

#: TES3 PKDT.Type of a wander package, the only kind whose idles the files drive.
_WANDER = 5

#: A placement's flag bit that a persistent actor's marker copies.
_PERSISTENT = 0x400

#: Vanilla furniture markers (SitTarget), Skyrim.esm FormIDs.
_CHAIR, _LEDGE, _CROSS, _LAY = 0x0006411B, 0x000C4827, 0x000C4EFD, 0x000C482E
_PRAY, _PICKAXE, _HAMMER = 0x000F11E9, 0x000E2BC7, 0x000C4328

#: Vanilla idle markers (UseIdleMarker), Skyrim.esm FormIDs.
_SWEEP, _BOOK, _DRINK = 0x00064106, 0x0007872B, 0x00097539

#: Idle markers vanilla lacks, built from vanilla idles: EditorID -> (timer, IDLE FormIDs).
_NEW_MARKERS = {
    'TES3DanceIdleMarker': (0.0, (0x000F7C8A, 0x000F7C8B, 0x00103653)),
    'TES3CoughIdleMarker': (10.0, (0x000D8736,)),
    'TES3GroundPickupIdleMarker': (10.0, (0x00075C3E,)),
}

#: The bounds every vanilla idle marker carries.
_IDLM_OBND = struct.pack('<6h', -54, -54, 0, 54, 89, 13)

_DANCE = 'TES3DanceIdleMarker'

#: Animation file -> (marker, package kind, yaw degrees, local x, y, z); offsets put the pelvises together.
_FILES = {
    'arktwend/ani/sitzgespräch.nif': (_CHAIR, MARKER_SIT, 3, 2.5, -2.4, 8.8),
    'arktwend/ani/sitzdrohen.nif': (_CHAIR, MARKER_SIT, 4, 2.5, -2.2, 10.1),
    'arktwend/ani/anim_sit.nif': (_CHAIR, MARKER_SIT, 4, 2.5, -2.2, 10.1),
    'arktwend/ani/sitzenbein.nif': (_CHAIR, MARKER_SIT, 78, -22.8, -29.5, 6.3),
    'am/am_eater.nif': (_CHAIR, MARKER_SIT, 3, 2.3, -2.4, 14.1),
    'am/am_luteplaying.nif': (_CHAIR, MARKER_SIT, 4, 2.3, 1.2, 14.5),
    'am/am_fishman.nif': (_LEDGE, MARKER_SIT, 7, -3.3, 0.7, 4.0),
    'am/am_beggar.nif': (_CROSS, MARKER_SIT, -12, -6.8, 3.4, -0.6),
    'am/am_dreamera.nif': (_CROSS, MARKER_SIT, -26, -6.9, 1.7, 1.5),
    'arktwend/ani/schlafen.nif': (_LAY, MARKER_SIT, 14, 34.7, -6.8, 4.2),
    'arktwend/ani/schlafenm.nif': (_LAY, MARKER_SIT, 38, -20.4, 12.9, 5.2),
    'arktwend/ani/liegenm_br.nif': (_LAY, MARKER_SIT, 3, 4.4, 12.7, 0.1),
    'am/ii/prayerdf.nif': (_PRAY, MARKER_SIT, 9, -0.8, -5.9, 8.4),
    'am/ii/miner.nif': (_PICKAXE, MARKER_SIT, 0, -5.9, 12.8, 5.1),
    'am/am_smith.nif': (_HAMMER, MARKER_SIT, 0, 0.2, 0.4, 8.8),
    'am/am_sweeping.nif': (_SWEEP, MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'am/am_reader1.nif': (_BOOK, MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'arktwend/ani/bar.nif': (_DRINK, MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'arktwend/ani/bar2.nif': (_DRINK, MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'arktwend/ani/trinken0x2.nif': (_DRINK, MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'am/am_cough.nif': ('TES3CoughIdleMarker', MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'am/ii/farmer.nif': ('TES3GroundPickupIdleMarker', MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    'am/ii/farmer2.nif': ('TES3GroundPickupIdleMarker', MARKER_IDLE, 0, 0.0, 0.0, 0.0),
    **{f'{path}.nif': (_DANCE, MARKER_IDLE, 0, 0.0, 0.0, 0.0) for path in (
        'anim_dancinggirl', 'arktwend/ani/tanzdynamic', 'arktwend/ani/tanzsexlo',
        'arktwend/ani/tanzsexfnb', 'arktwend/ani/xtanzsexfnb', 'arktwend/ani/rocknroll',
        'arktwend/ani/rocknrolla', 'arktwend/ani/hüpfen', 'arktwend/ani/aliroman',
        'arktwend/ani/aliroman2', 'arktwend/ani/sexgehen0x2')},
}


def file_entry(rec: dict):
    """The marker row of an NPC's own animation file, or None."""
    path = (rec.get('MorrowindAnim') or '').replace(chr(92) * 2, '/').replace(chr(92), '/')
    return _FILES.get(path.strip().lower())


def _wander_of(npc: dict, packs: dict):
    """The NPC's first wander package record, or None."""
    for index in range(get_int(npc, 'AIPackageCount', 0)):
        pack = packs.get(npc.get(f'AIPackage[{index}]', ''))
        if pack is not None and get_int(pack, 'PKDT.Type', -1) == _WANDER:
            return pack
    return None


def _marked_npcs(by_type: dict, placed: set) -> dict:
    """{NPC FormID: marker row} for NPCs whose wander package now runs on their marker.

    A package is flagged when every NPC running it maps to the same package
    kind and is placed by this plugin (one spawned by a script has no marker
    to link); any other keeps its Sandbox.
    """
    packs = {p.get('FormID'): p for p in by_type.get('PACK', [])}
    users = {}
    for npc in by_type.get('NPC_', []):
        pack = _wander_of(npc, packs)
        if pack is not None:
            row = file_entry(npc) if npc['FormID'] in placed else None
            users.setdefault(pack['FormID'], []).append((npc['FormID'], row))
    out = {}
    for pack_id, members in users.items():
        kinds = {row[1] if row else None for _n, row in members}
        if len(kinds) == 1 and None not in kinds:
            packs[pack_id][MARKER_KEY] = kinds.pop()
            out.update(members)
    return out


def _turn(x: float, y: float, yaw: float) -> tuple:
    """A local xy offset in the world, for a reference turned clockwise by `yaw`."""
    return (x * math.cos(yaw) + y * math.sin(yaw), -x * math.sin(yaw) + y * math.cos(yaw))


def _marker_ref(achr: dict, row: tuple, raw: int, base: int) -> dict:
    """A marker reference at the placement, turned and shifted so the poses meet."""
    yaw = float(achr.get('RotZ') or 0)
    dx, dy = _turn(row[3], row[4], yaw)
    persistent = get_int(achr, 'RecordFlags') & _PERSISTENT
    return {'Signature': 'REFR', 'FormID': '%08X' % raw, 'NAME': '00000000',
            'NAME.Final': '%08X' % base, 'RecordFlags': str(persistent),
            'ParentCELL': achr.get('ParentCELL', ''),
            'PosX': str(float(achr.get('PosX') or 0) + dx),
            'PosY': str(float(achr.get('PosY') or 0) + dy),
            'PosZ': str(float(achr.get('PosZ') or 0) + row[5]),
            'RotX': '0', 'RotY': '0', 'RotZ': str(yaw + math.radians(row[2]))}


def _idle_marker(fid: int, edid: str) -> bytes:
    """A new IDLM: EDID OBND IDLF IDLC IDLT IDLA, the vanilla layout (no model)."""
    timer, idles = _NEW_MARKERS[edid]
    subs = pack_string_subrecord('EDID', edid)
    subs += pack_subrecord('OBND', _IDLM_OBND)
    subs += pack_subrecord('IDLF', b'\x00')
    subs += pack_subrecord('IDLC', bytes([len(idles)]))
    subs += pack_subrecord('IDLT', struct.pack('<f', timer))
    subs += pack_subrecord('IDLA', b''.join(struct.pack('<I', i) for i in idles))
    return pack_record('IDLM', fid, 0, subs)


#: The marker REFRs planned this run, held back from the navmesh pass (flush_npc_markers).
_PENDING: list = []


def place_npc_markers(by_type: dict, writer, own_index: int) -> int:
    """Plan a marker for every own placement of a marked NPC; how many.

    Flags wander packages (MARKER_KEY) and sets each placement's
    `XLKR.Reference` before the package converter runs; the REFRs wait for
    flush_npc_markers, so no navmesh input changes.
    """
    _PENDING.clear()
    own = [a for a in by_type.get('ACHR', []) if int(a['FormID'], 16) >> 24 == own_index]
    marked = _marked_npcs(by_type, {a.get('NAME') for a in own})
    added, built = _PENDING, {}
    for achr in own:
        row = marked.get(achr.get('NAME'))
        if row is None:
            continue
        base = row[0]
        if isinstance(base, str):
            if base not in built:
                built[base] = writer.derive_formid(_IDLM_SITE, base)
                writer.add_record('IDLM', _idle_marker(built[base], base))
            base = built[base]
        fid = writer.derive_formid(_REF_SITE, achr['FormID'])
        raw = (own_index << 24) | (fid & 0xFFFFFF)
        added.append(_marker_ref(achr, row, raw, base))
        achr['XLKR.Reference'] = '%08X' % raw
    return len(added)


def flush_npc_markers(by_type: dict) -> int:
    """Append the planned marker REFRs for the cell builders; how many."""
    by_type.setdefault('REFR', []).extend(_PENDING)
    count = len(_PENDING)
    _PENDING.clear()
    return count


def linked_ref_subrecord(rec: dict) -> bytes:
    """A placement's XLKR to its marker (no keyword), or b''."""
    ref = get_formid(rec, 'XLKR.Reference')
    return pack_subrecord('XLKR', struct.pack('<II', 0, ref)) if ref else b''


def final_base(rec: dict):
    """A generated reference's base FormID, already in the output's space, or None."""
    value = rec.get('NAME.Final')
    return int(value, 16) if value else None
