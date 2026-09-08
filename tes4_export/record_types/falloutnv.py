"""
FO3/FNV export deltas: the subrecords Oblivion never emits.

Only fields whose FO3/FNV layout differs from TES4, or that TES4 lacks
entirely, live here. Everything the two games share is dumped by the
regular per-type exporters in this package.

See: docs/commentary/tes4_export_falloutnv.md
"""

import struct

from ..tes4_reader import (Record, get_all_subrecords,
                           get_formid_str, get_string,
                           get_subrecord)
from .common import (emit_float, emit_model, emit_raw_hex,
                     emit_script, emit_string, emit_u16, emit_u32)

#: HEDR.Version reported by FO3/FNV plugins; Oblivion reports 0.8 or 1.0.
FALLOUT_HEDR_MIN = 1.2


def is_fallout(hedr_version: float) -> bool:
    """True when a plugin's HEDR version marks it FO3/FNV rather than TES4."""
    return hedr_version >= FALLOUT_HEDR_MIN


def _emit_obnd(lines: list, rec: Record):
    """OBND (12B) -> six s16 bounds; Skyrim-native, so it passes through."""
    obnd = get_subrecord(rec, "OBND")
    if obnd and len(obnd.data) >= 12:
        x1, y1, z1, x2, y2, z2 = struct.unpack_from("<6h", obnd.data, 0)
        lines.append(f"OBND.X1={x1}")
        lines.append(f"OBND.Y1={y1}")
        lines.append(f"OBND.Z1={z1}")
        lines.append(f"OBND.X2={x2}")
        lines.append(f"OBND.Y2={y2}")
        lines.append(f"OBND.Z2={z2}")


def _emit_cell_deltas(lines: list, rec: Record):
    """CELL's FO3/FNV-only fields: the land-flag byte and the water noise texture."""
    xclc = get_subrecord(rec, "XCLC")
    if xclc and len(xclc.data) >= 12:
        lines.append(f"XCLC.LandFlags={xclc.data[8]}")

    xcll = get_subrecord(rec, "XCLL")
    if xcll and len(xcll.data) >= 40:
        lines.append(f"XCLL.FogPower={struct.unpack_from('<f', xcll.data, 36)[0]}")

    xnam = get_subrecord(rec, "XNAM")
    if xnam and len(xnam.data) > 1:
        lines.append(f"XNAM.WaterNoiseTexture={get_string(xnam)}")


def _emit_refr_deltas(lines: list, rec: Record):
    """REFR's FO3/FNV-only placement fields that map onto Skyrim equivalents."""
    xprm = get_subrecord(rec, "XPRM")
    if xprm and len(xprm.data) >= 32:
        bx, by, bz = struct.unpack_from("<3f", xprm.data, 0)
        lines.append(f"XPRM.BoundX={bx}")
        lines.append(f"XPRM.BoundY={by}")
        lines.append(f"XPRM.BoundZ={bz}")

    xrds = get_subrecord(rec, "XRDS")
    if xrds and len(xrds.data) >= 4:
        lines.append(f"XRDS.Radius={struct.unpack_from('<f', xrds.data, 0)[0]}")

    xemi = get_subrecord(rec, "XEMI")
    if xemi and len(xemi.data) >= 4:
        lines.append(f"XEMI.Emittance={get_formid_str(struct.unpack_from('<I', xemi.data, 0)[0])}")

    xlkr = get_subrecord(rec, "XLKR")
    if xlkr and len(xlkr.data) >= 4:
        lines.append(f"XLKR.LinkedRef={get_formid_str(struct.unpack_from('<I', xlkr.data, 0)[0])}")


#: FO3/FNV weapon anim type -> the equivalent TES4 DATA.Type.
_FALLOUT_WEAPON_TYPE = {
    0: 0, 1: 0, 2: 1, 3: 5, 4: 5, 5: 5, 6: 5,
    7: 5, 8: 1, 9: 5, 10: 5, 11: 5, 12: 5, 13: 5,
}

#: FO3/FNV anim types that are firearms rather than melee, by hand count.
FALLOUT_PISTOL_TYPES = frozenset({3, 4, 10, 11, 12, 13})
FALLOUT_LONGARM_TYPES = frozenset({5, 6, 7, 9})


def _emit_weap_deltas(lines: list, rec: Record):
    """WEAP's FO3/FNV layout: DATA carries the economy, DNAM the animation.

    TES4 packs both into one DATA; the keys emitted here are the TES4 ones so
    the importer needs no new vocabulary for the shared fields.

    See: docs/commentary/tes4_export_falloutnv.md#weapons-guns-become-crossbows
    """
    dnam = get_subrecord(rec, "DNAM")
    if dnam and len(dnam.data) >= 12:
        anim = struct.unpack_from("<I", dnam.data, 0)[0]
        lines.append(f"DATA.Type={_FALLOUT_WEAPON_TYPE.get(anim, 0)}")
        lines.append(f"DNAM.FalloutAnimType={anim}")
        lines.append(f"DATA.Speed={struct.unpack_from('<f', dnam.data, 4)[0]}")
        lines.append(f"DATA.Reach={struct.unpack_from('<f', dnam.data, 8)[0]}")

    data = get_subrecord(rec, "DATA")
    if data and len(data.data) >= 15:
        d = data.data
        lines.append(f"DATA.Value={struct.unpack_from('<i', d, 0)[0]}")
        lines.append(f"DATA.Health={struct.unpack_from('<i', d, 4)[0]}")
        lines.append(f"DATA.Weight={struct.unpack_from('<f', d, 8)[0]}")
        lines.append(f"DATA.Damage={struct.unpack_from('<h', d, 12)[0]}")
        lines.append(f"DATA.ClipSize={d[14]}")


def _emit_wrld_deltas(lines: list, rec: Record):
    """WRLD fields TES4 lacks: parent-use flags, map offset, LOD water, defaults.

    See: docs/commentary/tes4_export_falloutnv.md#child-worldspaces
    """
    emit_u16(lines, "PNAM.Flags", get_subrecord(rec, "PNAM"))
    onam = get_subrecord(rec, "ONAM")
    if onam and len(onam.data) >= 12:
        emit_float(lines, "ONAM.Scale", onam, 0)
        emit_float(lines, "ONAM.CellXOffset", onam, 4)
        emit_float(lines, "ONAM.CellYOffset", onam, 8)
    emit_float(lines, "NAM4.LODWaterHeight", get_subrecord(rec, "NAM4"))
    dnam = get_subrecord(rec, "DNAM")
    if dnam and len(dnam.data) >= 8:
        emit_float(lines, "DNAM.DefaultLandHeight", dnam, 0)
        emit_float(lines, "DNAM.DefaultWaterHeight", dnam, 4)


def _emit_navm_deltas(lines: list, rec: Record):
    """NAVM's authored geometry: the cell it covers, its vertices and triangles.

    FO3/FNV ship real navmeshes where TES4 has only pathgrids, so this is
    authored data to repack rather than geometry to generate. NVVX/NVTR/NVDP
    are dumped verbatim; the importer reinterprets them into TES5's NVNM blob.

    See: docs/commentary/tes4_export_falloutnv.md#navmesh-authored-not-generated
    """
    data = get_subrecord(rec, "DATA")
    if data and len(data.data) >= 24:
        cell, nvert, ntri, nedge, ncover, ndoor = struct.unpack_from(
            "<6I", data.data, 0)
        lines.append(f"DATA.Cell={get_formid_str(cell)}")
        lines.append(f"DATA.VertexCount={nvert}")
        lines.append(f"DATA.TriangleCount={ntri}")
        lines.append(f"DATA.EdgeLinkCount={nedge}")
        lines.append(f"DATA.CoverTriangleCount={ncover}")
        lines.append(f"DATA.DoorLinkCount={ndoor}")

    for sig in ("NVVX", "NVTR", "NVDP"):
        emit_raw_hex(lines, sig, get_subrecord(rec, sig))


def _emit_navi_deltas(lines: list, rec: Record):
    """NAVI's per-navmesh info entries, one NVMI blob per line.

    NVMI repeats thousands of times in a single record, so each is emitted
    with its ordinal plus a total count.

    See: docs/commentary/tes4_export_falloutnv.md#navmesh-authored-not-generated
    """
    index = 0
    for sub_rec in rec.subrecords:
        if sub_rec.type != "NVMI":
            continue
        lines.append(f"NVMI[{index}]={sub_rec.data.hex().upper()}")
        index += 1
    lines.append(f"NVMI.Count={index}")


#: TES4-layout actor keys the FO3/FNV ACBS/DATA emitters below supersede.
SUPERSEDED_ACTOR_KEYS = (
    "ACBS.SpellPoints=", "ACBS.Fatigue=", "ACBS.BarterGold=", "ACBS.Level=",
    "ACBS.CalcMin=", "ACBS.CalcMax=",
    "DATA.Soul=", "DATA.Health=", "DATA.AttackDamage=",
)

#: FO3/FNV ACBS is 24 bytes and drops TES4's SpellPoints; TES4's is 16.
_FALLOUT_ACBS_SIZE = 24

#: Template Flags bit 6, 'Model/Animation' (wbDefinitionsCommon.pas:7715).
TEMPLATE_USE_MODEL = 1 << 6

#: FO3/FNV creature DATA attribute order; TES4's CREA DATA has none of these.
_CREA_ATTRIBUTES = ("Strength", "Perception", "Endurance", "Charisma",
                    "Intelligence", "Agility", "Luck")


def _emit_actor_acbs(lines: list, rec: Record):
    """FO3/FNV ACBS, whose fields sit two bytes earlier than TES4's.

    TES4 spends bytes 4-5 on SpellPoints; FO3/FNV has no such field and puts
    Fatigue there, shifting everything after it. Reading the TES4 layout
    yields a plausible-looking record made entirely of neighbouring fields.
    Template Flags at 22 has no TES4 counterpart at all.

    See: docs/commentary/tes4_export_falloutnv.md#acbs-lost-its-spellpoints
    """
    acbs = get_subrecord(rec, "ACBS")
    if not acbs or len(acbs.data) < _FALLOUT_ACBS_SIZE:
        return
    d = acbs.data
    fatigue, gold, level, calc_min, calc_max, speed = struct.unpack_from(
        "<6H", d, 4)
    disposition, template_flags = struct.unpack_from("<hH", d, 20)
    lines.append(f"ACBS.Fatigue={fatigue}")
    lines.append(f"ACBS.BarterGold={gold}")
    lines.append(f"ACBS.Level={level}")
    lines.append(f"ACBS.CalcMin={calc_min}")
    lines.append(f"ACBS.CalcMax={calc_max}")
    lines.append(f"ACBS.SpeedMultiplier={speed}")
    lines.append(f"ACBS.Karma={struct.unpack_from('<f', d, 16)[0]}")
    lines.append(f"ACBS.Disposition={disposition}")
    lines.append(f"ACBS.TemplateFlags={template_flags}")


def _emit_actor_template(lines: list, rec: Record):
    """TPLT, the actor this record inherits its unowned categories from.

    See: docs/commentary/tes4_export_falloutnv.md#tplt-carries-the-whole-actor
    """
    tplt = get_subrecord(rec, "TPLT")
    if tplt and len(tplt.data) >= 4:
        fid = struct.unpack_from("<I", tplt.data, 0)[0]
        lines.append(f"TPLT.Template={get_formid_str(fid)}")


def _emit_crea_deltas(lines: list, rec: Record):
    """FO3/FNV CREA: the shifted ACBS, its template, and a 17-byte DATA.

    TES4's CREA DATA is 20 bytes with Soul and 8 attributes; FO3/FNV's is 17
    with neither, so the shared exporter's >= 20 guard silently emits nothing.
    """
    _emit_actor_acbs(lines, rec)
    _emit_actor_template(lines, rec)
    data = get_subrecord(rec, "DATA")
    if not data or len(data.data) < 17:
        return
    d = data.data
    lines.append(f"DATA.Health={struct.unpack_from('<h', d, 4)[0]}")
    lines.append(f"DATA.AttackDamage={struct.unpack_from('<h', d, 8)[0]}")
    for i, name in enumerate(_CREA_ATTRIBUTES):
        lines.append(f"DATA.{name}={d[10 + i]}")


def _emit_npc_deltas(lines: list, rec: Record):
    """FO3/FNV NPC_: the same shifted ACBS and template pointer as CREA."""
    _emit_actor_acbs(lines, rec)
    _emit_actor_template(lines, rec)


#: Per-type delta emitters, consulted by format_record only for FO3/FNV sources.
_DELTA_DISPATCH = {
    "CELL": _emit_cell_deltas,
    "REFR": _emit_refr_deltas,
    "WEAP": _emit_weap_deltas,
    "NAVM": _emit_navm_deltas,
    "NAVI": _emit_navi_deltas,
    "WRLD": _emit_wrld_deltas,
    "CREA": _emit_crea_deltas,
    "NPC_": _emit_npc_deltas,
}

#: Types carrying an OBND that TES4 has no field for; Skyrim reads it natively.
_OBND_TYPES = frozenset({
    "STAT", "DOOR", "ACTI", "CONT", "FURN", "LIGH", "MISC", "KEYM",
    "BOOK", "TREE", "GRAS", "FLOR", "ALCH", "AMMO", "ARMO", "WEAP",
})


def export_deltas(rec: Record) -> list:
    """The FO3/FNV-only lines for one record, appended after its TES4 export."""
    lines = []
    if rec.type in _OBND_TYPES:
        _emit_obnd(lines, rec)
    handler = _DELTA_DISPATCH.get(rec.type)
    if handler:
        handler(lines, rec)
    return lines


def export_STATIC_BASE(rec: Record) -> list:
    """A model-only FO3/FNV base object, converted as a Skyrim STAT.

    MSTT, SCOL, PWAT and IDLM all reduce to a model plus bounds. They are the
    base objects of 10,000+ placed references; without them those REFRs have a
    null base and the engine faults promoting them into their location.

    See: docs/commentary/tes4_export_falloutnv.md#fallout-only-base-objects
    """
    lines = []
    emit_string(lines, "EditorID", get_subrecord(rec, "EDID"))
    emit_model(lines, "Model", rec)
    _emit_obnd(lines, rec)
    return lines


def export_ACTIVATOR_BASE(rec: Record) -> list:
    """A named, scriptable FO3/FNV base object, converted as a Skyrim ACTI.

    TERM, NOTE and TACT are activators in all but signature: each carries a
    model, a display name and (for TACT/TERM) a script.

    See: docs/commentary/tes4_export_falloutnv.md#fallout-only-base-objects
    """
    lines = []
    emit_string(lines, "EditorID", get_subrecord(rec, "EDID"))
    emit_string(lines, "FULL", get_subrecord(rec, "FULL"))
    emit_model(lines, "Model", rec)
    emit_script(lines, rec)
    _emit_obnd(lines, rec)
    return lines


#: FO3/FNV base-object types Oblivion lacks -> the exporter that reduces them.
def export_NAVMESH(rec: Record) -> list:
    """A navmesh record's identity; export_deltas emits its geometry."""
    lines = []
    emit_string(lines, "EditorID", get_subrecord(rec, "EDID"))
    return lines


def export_MESSAGE(rec: Record) -> list:
    """A FO3/FNV MESG, which Skyrim carries as the same record type.

    DESC/INAM/DNAM are required on the TES5 side; ITXT repeats once per button.

    See: docs/commentary/tes4_export_falloutnv.md#mesg-export
    """
    lines = []
    emit_string(lines, "EditorID", get_subrecord(rec, "EDID"))
    emit_string(lines, "DESC", get_subrecord(rec, "DESC"))
    emit_string(lines, "FULL", get_subrecord(rec, "FULL"))
    emit_u32(lines, "DNAM", get_subrecord(rec, "DNAM"))
    for i, sub in enumerate(get_all_subrecords(rec, "ITXT")):
        emit_string(lines, f"Button[{i}].Text", sub)
    return lines


FALLOUT_BASE_EXPORTERS = {
    "MESG": export_MESSAGE,
    "NAVM": export_NAVMESH,
    "NAVI": export_NAVMESH,
    "MSTT": export_STATIC_BASE,
    "SCOL": export_STATIC_BASE,
    "PWAT": export_STATIC_BASE,
    "IDLM": export_STATIC_BASE,
    "ASPC": export_STATIC_BASE,
    "TERM": export_ACTIVATOR_BASE,
    "NOTE": export_ACTIVATOR_BASE,
    "TACT": export_ACTIVATOR_BASE,
}
