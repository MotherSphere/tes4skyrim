"""Bethesda 20.2 `num_uv_sets` is a flag bit, not a 6-bit count.

pyffi sizes the UV array as `num_uv_sets & 63`, which folds Havok Material's
low two bits into the count on `#BS202#` files. Havok material 63 asked for 33
UV arrays where the file has 1, so 32 FalloutNV meshes read past EOF.

See: docs/commentary/asset_convert_nif.md#bethesda-geometry-data-flags
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asset_convert.nif.pyffi_monkey_patch import apply_patches
apply_patches()
from pyffi.formats.nif import NifFormat

FNV = (0x14020007, 34)
OBLIVION = (0x14000004, 11)


def _data(version, uv2):
    """A NifFormat.Data stamped with one game's version pair."""
    d = NifFormat.Data()
    d.version, d.user_version, d.user_version_2 = version, 11, uv2
    d._link_stack = []
    return d


def _shape(uv_flag_byte, verts=3):
    """A NiTriShapeData whose raw num_uv_sets byte is `uv_flag_byte`."""
    b = NifFormat.NiTriShapeData()
    b.num_vertices = verts
    b.has_vertices = True
    b.vertices.update_size()
    b.num_uv_sets = uv_flag_byte
    b.uv_sets.update_size()
    return b


def _roundtrip(block, data):
    """(block re-read from its own bytes, those bytes)."""
    buf = io.BytesIO()
    block.write(buf, data)
    buf.seek(0)
    out = type(block)()
    out.read(buf, data)
    return out, buf.getvalue()


@pytest.mark.parametrize('material_bits', [0x00, 0x40, 0x80, 0xC0])
def test_havok_material_never_inflates_uv_count(material_bits):
    """Only bit 0 counts UV sets; material bits 6-7 must not leak into it."""
    data = _data(*FNV)
    block = _shape(0x01 | material_bits)
    out, _ = _roundtrip(block, data)
    assert out.num_uv_sets == 1
    assert len(out.uv_sets) == 1


def test_has_uv_zero_reads_no_uv_sets():
    """Bit 0 clear means the file stores no UV array at all."""
    data = _data(*FNV)
    out, _ = _roundtrip(_shape(0xC0), data)
    assert out.num_uv_sets == 0
    assert len(out.uv_sets) == 0


def test_havok_material_survives_a_read_then_write():
    """Material bits stashed on read go back out, so re-writing is lossless."""
    data = _data(*FNV)
    source = _shape(0x01 | 0xC0)
    source._num_uv_sets_value_._havok_material = 0xC0
    buf = io.BytesIO()
    source.write(buf, data)
    original = buf.getvalue()

    parsed = NifFormat.NiTriShapeData()
    parsed.read(io.BytesIO(original), data)
    assert parsed.num_uv_sets == 1

    again = io.BytesIO()
    parsed.write(again, data)
    assert again.getvalue() == original


def test_oblivion_keeps_pyffis_six_bit_count():
    """20.0.0.4 is NiGeometryDataFlags, where the low 6 bits really are a count."""
    data = _data(*OBLIVION)
    out, _ = _roundtrip(_shape(0x02), data)
    assert out.num_uv_sets == 2
    assert len(out.uv_sets) == 2
