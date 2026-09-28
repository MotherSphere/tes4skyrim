"""TES4 Confidence in Skyrim: no strength-based fleeing, an own-health flee threshold.

Oblivion flees once an actor has lost Confidence% of its OWN health; Skyrim's
tiers 0-3 flee by comparing the actor's strength with its enemy's, which no
Oblivion actor ever did. Every converted actor is therefore Cowardly (0) or
Foolhardy (4), and one in between carries its threshold as a rank in a hidden
faction read by a conditioned ability (`TES4ConfidenceFlee`).

See: docs/commentary/tes5_import_actors.md#confidence-tiers
"""

import struct

from ..base.conditions import build_ctda
from ..base.text_reader import get_int
from .combat_style import fleeing_disabled
from ..base.writer import (PluginWriter, pack_formid_subrecord, pack_obnd,
                           pack_record, pack_string_subrecord, pack_subrecord)

#: The hidden faction whose rank is the actor's TES4 confidence (1-99).
FACTION_EDID = 'TES4ConfidenceFaction'

#: The constant ability whose effects fire once the owner's health is low enough.
FLEE_SPELL_EDID = 'TES4ConfidenceFlee'

#: The ability's script effect and the ActiveMagicEffect script it carries.
FLEE_EFFECT_EDID = 'TES4ConfidenceFleeEffect'
FLEE_SCRIPT = 'TES4_ConfidenceFlee'

#: wbConfidenceEnum tiers the conversion writes.
TIER_COWARDLY, TIER_FOOLHARDY = 0, 4

#: TES4 confidence at which Oblivion never flees.
_NEVER_FLEES = 100

#: CTDA functions and the Health actor value (vanilla GetActorValuePercent(00000018)).
_FUNC_GET_FACTION_RANK, _FUNC_GET_AV_PERCENT, _AV_HEALTH = 73, 640, 24

#: CTDA comparison operators <= and >=.
_OP_LE, _OP_GE = 0xA0, 0x60

#: MGEF flags of vanilla's constant self script holders (WereFXFeedBloodHolder): Hide in UI | FX Persist | No Duration.
_EFFECT_FLAGS = 0x9200

#: MGEF archetype 1 Script; casting 0 Constant Effect; delivery 0 Self; SPIT type 4 Ability.
_ARCHETYPE_SCRIPT, _CONSTANT, _SELF, _ABILITY = 1, 0, 0, 4

#: ETYP EitherHand, which vanilla abilities carry.
_EITHER_HAND = 0x00013F44

#: FACT DATA flag 0x1: Hidden From PC.
_HIDDEN_FROM_PC = 0x1

#: FormIDs of this run's faction and ability (0 until created or adopted).
_FIDS = {FACTION_EDID: 0, FLEE_SPELL_EDID: 0}


def actor_confidence(rec: dict) -> int:
    """The actor's TES4 confidence; 100 when its combat style disables fleeing."""
    return _NEVER_FLEES if fleeing_disabled(rec) else get_int(rec, 'AIDT.Confidence')


def confidence_tier(confidence: int) -> int:
    """TES4 confidence 0-100 as a TES5 tier: Cowardly at 0, else Foolhardy."""
    return TIER_COWARDLY if confidence <= 0 else TIER_FOOLHARDY


def flee_rank(confidence: int) -> int:
    """The faction rank carrying an own-health threshold, 0 when none applies."""
    return confidence if 0 < confidence < _NEVER_FLEES else 0


def flee_memberships(confidence: int) -> list:
    """[(faction FormID, rank)] an actor with this confidence joins."""
    rank = flee_rank(confidence)
    fid = _FIDS[FACTION_EDID]
    return [(fid, rank)] if rank and fid else []


def flee_spells(confidence: int) -> list:
    """The flee ability, for an actor whose confidence carries a threshold."""
    fid = _FIDS[FLEE_SPELL_EDID]
    return [fid] if flee_rank(confidence) and fid else []


def _faction(fid: int) -> bytes:
    """The hidden, relation-free rank holder."""
    subs = pack_string_subrecord('EDID', FACTION_EDID)
    subs += pack_subrecord('DATA', struct.pack('<I', _HIDDEN_FROM_PC))
    return pack_record('FACT', fid, 0, subs)


def _effect(fid: int, faction: int) -> bytes:
    """The constant self Script effect carrying TES4_ConfidenceFlee."""
    from script_convert.pipeline import build_vmad_object_script
    data = bytearray(152)
    struct.pack_into('<I', data, 0, _EFFECT_FLAGS)
    struct.pack_into('<ii', data, 12, -1, -1)
    struct.pack_into('<Ii', data, 64, _ARCHETYPE_SCRIPT, -1)
    struct.pack_into('<II', data, 80, _CONSTANT, _SELF)
    struct.pack_into('<i', data, 88, -1)
    struct.pack_into('<f', data, 104, 1.0)
    subs = pack_string_subrecord('EDID', FLEE_EFFECT_EDID)
    subs += pack_subrecord('VMAD', build_vmad_object_script(
        FLEE_SCRIPT, {FACTION_EDID: faction}))
    subs += pack_subrecord('DATA', bytes(data))
    return pack_record('MGEF', fid, 0, subs)


def _threshold_effect(effect: int, faction: int, rank: int) -> bytes:
    """Effect k: active while rank <= k and health <= 1 - k/100, so rank r flees at 1 - r/100."""
    subs = pack_formid_subrecord('EFID', effect)
    subs += pack_subrecord('EFIT', struct.pack('<fII', 0.0, 0, 0))
    subs += pack_subrecord('CTDA', build_ctda(
        _FUNC_GET_AV_PERCENT, _AV_HEALTH, 0, 1.0 - rank / 100.0, _OP_LE))
    subs += pack_subrecord('CTDA', build_ctda(
        _FUNC_GET_FACTION_RANK, faction, 0, float(rank), _OP_LE))
    return subs + pack_subrecord('CTDA', build_ctda(
        _FUNC_GET_FACTION_RANK, faction, 0, 1.0, _OP_GE))


def _ability(fid: int, effect: int, faction: int) -> bytes:
    """The constant ability with one threshold effect per rank 1-99."""
    subs = pack_string_subrecord('EDID', FLEE_SPELL_EDID)
    subs += pack_obnd()
    subs += pack_subrecord('ETYP', struct.pack('<I', _EITHER_HAND))
    subs += pack_subrecord('SPIT', struct.pack(
        '<IIIfII12x', 0, 0, _ABILITY, 0.0, _CONSTANT, _SELF))
    for rank in range(1, _NEVER_FLEES):
        subs += _threshold_effect(effect, faction, rank)
    return pack_record('SPEL', fid, 0, subs)


def create_confidence_records(writer: PluginWriter, master_index=None,
                              wanted: bool = True) -> dict:
    """The faction and flee ability, adopted from a master that has them.

    Returns {EditorID: FormID} for WELL_KNOWN_PROPERTIES; {} when not `wanted`
    (a Morrowind or FO3/FNV source, whose actors carry no threshold).
    See: docs/commentary/tes5_import_actors.md#morrowind-flee
    """
    _FIDS.update(dict.fromkeys(_FIDS, 0))
    if not wanted:
        return {}
    found = {edid: (master_index.find_by_edid(sig, edid)
                    if master_index is not None else 0)
             for sig, edid in ((b'FACT', FACTION_EDID), (b'SPEL', FLEE_SPELL_EDID))}
    if not all(found.values()):
        found[FACTION_EDID] = writer.derive_formid('FACT', FACTION_EDID)
        effect = writer.derive_formid('MGEF', FLEE_EFFECT_EDID)
        found[FLEE_SPELL_EDID] = writer.derive_formid('SPEL', FLEE_SPELL_EDID)
        writer.add_record('FACT', _faction(found[FACTION_EDID]))
        writer.add_record('MGEF', _effect(effect, found[FACTION_EDID]))
        writer.add_record('SPEL', _ability(found[FLEE_SPELL_EDID], effect,
                                           found[FACTION_EDID]))
    _FIDS.update(found)
    return dict(found)
