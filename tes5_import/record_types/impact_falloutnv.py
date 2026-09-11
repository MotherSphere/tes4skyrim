"""FO3/FNV impacts: IPCT and IPDS records, so a gun's `INAM` names its own
ballistic impact set instead of the crossbow template's arrow set.

FNV's IPCT `DATA` (24 bytes) is byte-compatible with TES5's; the IPDS is
twelve IPCT slots in a fixed material order that map to Skyrim MATTs.
See: docs/commentary/tes4_export_falloutnv.md#impacts
"""

import struct

from ..base.writer import (pack_formid_subrecord, pack_record,
                      pack_string_subrecord, pack_subrecord)
from .common import get_formid, get_int, get_str, prefix_path
from .projectile_falloutnv import sndr_of

#: IPCT DATA flag bit 0: the impact places no decal.
_NO_DECAL_DATA = 0x01
#: Skyrim MATT FormIDs per FNV IPDS slot name, the vanilla material each names first.
IMPACT_SLOT_MATERIALS = (
    ('Stone', (0x12F34, 0x12F36, 0x12F35)),
    ('Dirt', (0x12F38, 0x1C151)),
    ('Grass', (0x12F46,)),
    ('Glass', (0x12F39,)),
    ('Metal', (0x12F3C, 0x624B4, 0x12F3A)),
    ('Wood', (0x12F42, 0x12F41)),
    ('Organic', (0x12F3F,)),
    ('Cloth', (0x12F37, 0x388FC)),
    ('Water', (0x12F40,)),
    ('HollowMetal', (0x12F3B,)),
    ('OrganicBug', (0x10D5CC,)),
    ('OrganicGlow', (0xD309F,)),
)


def convert_IPCT(rec: dict, writer=None) -> bytes:
    """A FNV IPCT as a TES5 IPCT: model, DATA with result Default and No
    Decal Data set (the decal TXSTs are not converted), both sounds as
    SNDRs."""
    subs = pack_string_subrecord('EDID', get_str(rec, 'EditorID'))
    model = get_str(rec, 'Model.MODL')
    if model:
        subs += pack_string_subrecord('MODL', prefix_path(model))
    data = bytearray(bytes.fromhex(get_str(rec, 'DATA') or '').ljust(24, b'\0')[:24])
    data[20] |= _NO_DECAL_DATA
    data[21:24] = b'\0\0\0'
    subs += pack_subrecord('DATA', bytes(data))
    for sig in ('SNAM', 'NAM1'):
        fid = sndr_of(writer, get_formid(rec, sig))
        if fid:
            subs += pack_formid_subrecord(sig, fid)
    return pack_record('IPCT', get_formid(rec, 'FormID'),
                       get_int(rec, 'RecordFlags'), subs)


def convert_IPDS(rec: dict, writer=None) -> bytes:
    """A FNV IPDS as a TES5 IPDS: one PNAM (MATT, IPCT) pair per material
    each filled slot names."""
    subs = pack_string_subrecord('EDID', get_str(rec, 'EditorID'))
    for slot, materials in IMPACT_SLOT_MATERIALS:
        ipct = get_formid(rec, f'DATA.{slot}')
        if ipct:
            for matt in materials:
                subs += pack_subrecord('PNAM', struct.pack('<II', matt, ipct))
    return pack_record('IPDS', get_formid(rec, 'FormID'),
                       get_int(rec, 'RecordFlags'), subs)
