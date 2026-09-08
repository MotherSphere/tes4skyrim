"""FO3/FNV MESG — the record a converted `ShowMessage` binds to.

Skyrim carries MESG unchanged, so this is a straight carry-over rather than an
approximation. Oblivion has no MESG at all; the only ones a TES4 conversion
produces are SYNTHESIZED by `synth_records.create_message_menu_records` for
button MessageBox call sites, which is why the authored FO3/FNV records needed
a converter of their own.

See: docs/commentary/tes4_export_falloutnv.md#mesg-export
"""

from .common import (get_formid, get_int, get_str, pack_record,
                     pack_string_subrecord, pack_subrecord,
                     pack_uint32_subrecord)

#: DNAM bit 0 (Message Box); vanilla Skyrim writes 1 on every help message.
_MESSAGE_BOX = 1


def convert_MESG(rec: dict) -> bytes:
    """MESG — EDID, DESC, FULL, INAM, DNAM, then one ITXT per button.

    DESC, INAM and DNAM are `SetRequired` in the TES5 definition, so DESC falls
    back to the title and INAM is always written as the null FormID vanilla
    carries.
    """
    edid = get_str(rec, 'EditorID')
    full = get_str(rec, 'FULL')
    desc = get_str(rec, 'DESC') or full

    subs = b''
    if edid:
        subs += pack_string_subrecord('EDID', edid)
    subs += pack_string_subrecord('DESC', desc)
    if full:
        subs += pack_string_subrecord('FULL', full)
    subs += pack_subrecord('INAM', b'\x00\x00\x00\x00')
    subs += pack_uint32_subrecord('DNAM',
                                  get_int(rec, 'DNAM', _MESSAGE_BOX))

    i = 0
    while True:
        text = get_str(rec, f'Button[{i}].Text')
        if not text:
            break
        subs += pack_string_subrecord('ITXT', text)
        i += 1

    return pack_record('MESG', get_formid(rec, 'FormID'),
                       get_int(rec, 'RecordFlags'), subs)
