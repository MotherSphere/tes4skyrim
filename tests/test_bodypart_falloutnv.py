"""FO3/FNV body part data: export, TES5 record and the SKSE sidecar."""

import os
import struct

import pytest

from tes5_import.record_types.bodypart_falloutnv import (
    BPND_SEVERABLE, DEFAULT_BODY_PART_DATA, bptd_sidecar, convert_BPTD,
    limb_models, limb_static, translate_bpnd)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BPTD_TXT = os.path.join(REPO, 'export', 'FalloutNV.esm', 'BPTD.txt')


def _bptd_has_parts() -> bool:
    """True when the export carries real BPND part data, not just sizes.

    tes4_export has no BPTD handler, so it dumps `# Unknown record type`
    plus subrecord SIZES only; the sidecar has nothing to read until the
    exporter learns the record.
    """
    try:
        with open(BPTD_TXT, encoding='utf-8', errors='replace') as f:
            return 'BPND=' in f.read(200000)
    except OSError:
        return False


needs_fnv = pytest.mark.skipif(not _bptd_has_parts(),
                               reason='FalloutNV BPTD export has no part data '
                                      '(tes4_export lacks a BPTD handler)')


def _bpnd(part_type, flags=BPND_SEVERABLE, debris=0x1234):
    b = bytearray(84)
    struct.pack_into('<f', b, 0, 1.0)
    b[4] = flags
    struct.pack_into('<b', b, 5, part_type)
    struct.pack_into('<I', b, 32, debris)
    return bytes(b)


def _record(fid, parts):
    rec = {'FormID': f'{fid:08X}', 'EditorID': 'X', 'Signature': 'BPTD',
           'PartCount': str(len(parts))}
    for i, (name, node, bpnd) in enumerate(parts):
        rec[f'Part[{i}].Name'] = name
        rec[f'Part[{i}].Node'] = node
        rec[f'Part[{i}].Target'] = node
        rec[f'Part[{i}].IKStart'] = node
        rec[f'Part[{i}].BPND'] = bpnd.hex().upper()
        rec[f'Part[{i}].LimbReplacementModel'] = f'dismember\\{name}.nif'
        rec[f'Part[{i}].GoreTargetBone'] = node
    return rec


class TestRecord:
    def test_only_torso_and_head_reach_the_record(self):
        rec = _record(0x123456, [('Torso', 'Bip01 Spine1', _bpnd(0)),
                                 ('Head', 'Bip01 Head', _bpnd(1)),
                                 ('Left Arm', 'Bip01 L UpperArm', _bpnd(3))])
        out = convert_BPTD(rec, converted_types=())
        assert out.count(b'BPNN') == 2
        assert b'Bip01 L UpperArm' not in out

    def test_gore_bits_and_unconverted_refs_are_cleared(self):
        b = translate_bpnd(_bpnd(0, flags=0x0B, debris=0x1234), ())
        assert b[4] == 0x02 and b[5] == 0
        assert struct.unpack_from('<I', b, 32)[0] == 0

    def test_default_body_part_data_overrides_skyrims(self):
        rec = _record(DEFAULT_BODY_PART_DATA,
                      [('Torso', 'Bip01 Spine1', _bpnd(0)),
                       ('Head', 'Bip01 Head', _bpnd(1))])
        out = convert_BPTD(rec, converted_types=())
        assert struct.unpack_from('<I', out, 12)[0] == DEFAULT_BODY_PART_DATA
        assert b'NPC Spine1 [Spn1]' in out and b'NPC Head [Head]' in out

    def test_sidecar_keeps_every_limb(self):
        """Every part reaches the sidecar with its node, limb static and file."""
        rec = _record(DEFAULT_BODY_PART_DATA,
                      [('Torso', 'Bip01 Spine1', _bpnd(0, flags=0)),
                       ('Left Arm', 'Bip01 L UpperArm', _bpnd(3))])
        limbs = {m: 0x01ABCDEF for m in limb_models([rec])}
        side = bptd_sidecar(rec, 'FalloutNV.esm', limbs)
        assert side['formid'] == '0000001D' and side['humanoid']
        assert side['file'] == 'Skyrim.esm' and side['local'] == 0x1D
        arm = side['parts'][1]
        assert arm['type_name'] == 'LeftArm1' and arm['severable']
        assert arm['node'] == 'NPC L UpperArm [LUar]'
        assert arm['limb_model'].startswith('tes4\\')
        assert arm['limb_local'] == 0xABCDEF
        assert side['parts'][0]['severable'] is False

    def test_plugin_records_name_their_own_file(self):
        """A record with the plugin's index byte is owned by the plugin."""
        rec = _record(0x01234567, [('Torso', 'Bip01 Spine1', _bpnd(0))])
        side = bptd_sidecar(rec, 'FalloutNV.esm', {})
        assert side['file'] == 'FalloutNV.esm'

    def test_limb_static_is_a_movable_static_of_the_model(self):
        """The loose limb is an MSTT on the gore model, id from the path."""
        class Writer:
            """Stands in for the ESM writer's FormID derivation."""

            def derive_formid(self, site, key):
                """The fixed id, after checking the site."""
                assert site == 'BPTD_LIMB'
                return 0x01000ABC
        fid, rec = limb_static(Writer(), 'tes4\\gore\\gorearmgore01.nif')
        assert fid == 0x01000ABC and rec[:4] == b'MSTT'
        assert b'MODL' in rec and b'gorearmgore01.nif' in rec
        assert b'TES4Limbgorearmgore01' in rec


@needs_fnv
class TestExport:
    def test_default_body_part_data_exported_with_limbs(self):
        from tes5_import.base.text_reader import parse_export_file
        recs = {r.get('EditorID'): r for r in parse_export_file(BPTD_TXT)}
        rec = recs['DefaultBodyPartData']
        assert int(rec['FormID'], 16) == DEFAULT_BODY_PART_DATA
        side = bptd_sidecar(rec, 'FalloutNV.esm', {})
        names = {p['type_name'] for p in side['parts']}
        assert {'Torso', 'Head1', 'LeftArm1', 'RightLeg1'} <= names
        assert any(p['severable'] and p['limb_model'] for p in side['parts'])
