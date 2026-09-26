"""A plugin-authored race stands in as the known race whose face parts it shares.

See: docs/commentary/tes5_import_actors.md#new-races-by-face-parts
"""
from tes5_import.base.equivalents import TES4_RACE_FID_TO_EDID
from tes5_import.base.race_lookup import register_races, stand_ins, tes4_race_edid

_FID = {edid: fid for fid, edid in TES4_RACE_FID_TO_EDID.items()}
_HEAD = 'Characters\\Imperial\\headhuman.nif'


def _race(fid, *models):
    """A RACE export record authoring `models` as its face parts."""
    rec = {'Signature': 'RACE', 'FormID': '%08X' % fid}
    rec.update({f'FacePart[{i}].Model': m for i, m in enumerate(models)})
    return rec


def _known():
    """Imperial and Wood Elf, sharing the head but not the ears."""
    return [_race(_FID['Imperial'], _HEAD, 'Characters\\Imperial\\earshuman.nif'),
            _race(_FID['WoodElf'], _HEAD, 'Characters\\WoodElf\\earself.nif')]


def test_new_race_takes_the_race_whose_ears_it_wears():
    """Head plus elf ears matches Wood Elf by two parts, Imperial by one."""
    new = _race(0x01000ABC, _HEAD, 'characters/woodelf/EARSELF.nif')
    assert stand_ins(_known() + [new]) == {0x000ABC: 'WoodElf'}


def test_a_tie_keeps_the_callers_default():
    """Sharing only the head ties both races, so no stand-in is chosen."""
    new = _race(0x01000ABD, _HEAD, 'Characters\\Custom\\ears.nif')
    assert register_races(_known() + [new]) == 0
    assert tes4_race_edid(0x01000ABD, 'Imperial') == 'Imperial'


def test_lookup_ignores_the_load_order_index():
    """A registered stand-in resolves under any load-order index byte."""
    register_races(_known() + [_race(0x01000ABC, _HEAD, 'Characters\\WoodElf\\earself.nif')])
    assert tes4_race_edid(0x05000ABC) == 'WoodElf'
    assert tes4_race_edid(_FID['Imperial']) == 'Imperial'
