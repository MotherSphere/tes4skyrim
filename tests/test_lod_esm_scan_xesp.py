"""esm_scan reads each REFR's XESP enable parent: normalized id, opposite bit.

A chain of enable parents can cross plugins, so the parent id must be in the
same global index space as `form_id`.  The fixture registers the files in a
global order that DIFFERS from the plugin's own master order (Oblivion.esm is
index 01 in the file and 00 globally), so a reader that kept the raw id
returns a different number and the test can tell.
"""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asset_convert.lod import esm_scan

MASTERS = ('Skyrim.esm', 'Oblivion.esm')
OBLIVION, SKYRIM, OWN = 0x00000000, 0x02000000, 0x03000000


@pytest.fixture
def scan(monkeypatch):
    """esm_scan with a fresh file registry: Oblivion.esm 0, a filler 1, Skyrim.esm 2."""
    monkeypatch.setattr(esm_scan, '_GLOBAL_FILES', [])
    monkeypatch.setattr(esm_scan, '_GLOBAL_FILE_IDX', {})
    monkeypatch.setattr(esm_scan, '_MASTERS_CACHE', {})
    for name in ('Oblivion.esm', 'Filler.esm', 'Skyrim.esm'):
        esm_scan.global_file_index(name)
    return esm_scan


def _rec(sig: bytes, fid: int, body: bytes = b'', flags: int = 0) -> bytes:
    """One record: header plus `body`."""
    return sig + struct.pack('<IIIII', len(body), flags, fid, 0, 0) + body


def _grup(label: int, gtype: int, payload: bytes) -> bytes:
    """One GRUP around `payload`."""
    return (b'GRUP' + struct.pack('<I', 24 + len(payload))
            + struct.pack('<I', label) + struct.pack('<III', gtype, 0, 0)
            + payload)


def _sub(sig: bytes, payload: bytes) -> bytes:
    """One subrecord."""
    return sig + struct.pack('<H', len(payload)) + payload


def _plugin(tmp_path: Path, payload: bytes) -> Path:
    """A minimal `ov.esp` whose master list is MASTERS, so its own index is 02."""
    hdr = _sub(b'HEDR', struct.pack('<fII', 1.7, 0, 0x800)) + b''.join(
        _sub(b'MAST', m.encode() + b'\0') + _sub(b'DATA', bytes(8))
        for m in MASTERS)
    p = tmp_path / 'ov.esp'
    p.write_bytes(_rec(b'TES4', 0, hdr) + payload)
    return p


def _refr(fid: int, xesp: bytes = b'') -> bytes:
    """A REFR placing base 0x01000100, with an optional raw XESP payload."""
    body = (_sub(b'NAME', struct.pack('<I', 0x01000100))
            + _sub(b'DATA', struct.pack('<6f', 1, 2, 3, 0, 0, 0)))
    if xesp:
        body += _sub(b'XESP', xesp)
    return _rec(b'REFR', fid, body)


def test_xesp_parent_and_opposite_bit_are_read(scan, tmp_path):
    """Parent normalized per file; bit 0 alone decides `opposite`; no or short XESP is None."""
    refs = (_refr(0x02000002, struct.pack('<II', 0x01005820, 1))
            + _refr(0x02000003)
            + _refr(0x02000004, struct.pack('<II', 0x02000002, 0))
            + _refr(0x02000005, struct.pack('<II', 0x00000ABC, 0x24468202))
            + _refr(0x02000006, struct.pack('<II', 0x00000ABC, 0x24468203))
            + _refr(0x02000007, struct.pack('<I', 0x01005820)))
    payload = _grup(0x0100003C, 1, _grup(0x02000001, 6, refs))
    _w, _c, _s, got = scan.parse_esm(_plugin(tmp_path, payload))
    xesp = {r['form_id']: r['xesp'] for r in got}
    assert xesp == {OWN | 2: (OBLIVION | 0x005820, True),
                    OWN | 3: None,
                    OWN | 4: (OWN | 2, False),
                    OWN | 5: (SKYRIM | 0xABC, False),
                    OWN | 6: (SKYRIM | 0xABC, True),
                    OWN | 7: None}
    assert set(got[0]) == {'form_id', 'flags', 'base_fid', 'parent_wrld',
                           'parent_cell', 'x', 'y', 'z', 'rx', 'ry', 'rz',
                           'scale', 'xesp'}
