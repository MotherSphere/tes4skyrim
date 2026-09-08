"""FO3/FNV humanoid races mapped onto Skyrim playable races.

FNV races share no FormID with Oblivion's, so the Oblivion table misses on
every one of them and the actor falls back to a single race.  Caucasian is
0x00000019, which Oblivion's table already spends on VampireRace, so the two
cannot be merged into one dict.

The four ethnicities take the four distinct human races closest in skin tone
(_SKIN_FALLBACK_RGB): Nord is the lightest, Redguard by far the darkest,
Imperial the mid-brown between them.  Skyrim has no Asian race and no facial
structure to borrow, so Breton is chosen only to keep the four ethnicities on
four separate tints rather than collapsing 686 actors onto one.

Raider/Old/OldAged suffixes are texture and FaceGen variants of their base
ethnicity, not separate peoples, so they resolve to the same Skyrim race; the
per-actor face already rides on NPC_.FGGS.

See: docs/commentary/tes4_export_falloutnv.md#humanoid-races
"""

from .world_falloutnv import is_fallout_source

#: FNV ethnicity -> Oblivion race EditorID keying RACE_MAP and the face tables.
_FNV_ETHNIC_TO_EDID = {
    'Caucasian': 'Nord',
    'AfricanAmerican': 'Redguard',
    'Hispanic': 'Imperial',
    'Asian': 'Breton',
}

#: Appearance tiers layered on an ethnicity; stripped to find the base race.
_FNV_VARIANT_SUFFIXES = ('OldAged', 'Raider', 'Child', 'Old')

#: FNV RACE FormID -> EditorID, for the ids the export actually carries.
_FNV_RACE_FID_TO_EDID = {
    0x00000019: 'Caucasian',
    0x000038E5: 'Hispanic',
    0x000038E6: 'Asian',
    0x00003B3E: 'Ghoul',
    0x0000424A: 'AfricanAmerican',
    0x000042BE: 'AfricanAmericanChild',
    0x000042BF: 'AfricanAmericanOld',
    0x000042C0: 'AsianChild',
    0x000042C1: 'AsianOld',
    0x000042C2: 'CaucasianChild',
    0x000042C3: 'CaucasianOld',
    0x000042C4: 'HispanicChild',
    0x000042C5: 'HispanicOld',
    0x00033184: 'TestQACaucasian',
    0x0004BB8D: 'CaucasianRaider',
    0x0004BF70: 'HispanicRaider',
    0x0004BF71: 'AsianRaider',
    0x0004BF72: 'AfricanAmericanRaider',
    0x000987DC: 'HispanicOldAged',
    0x000987DD: 'AsianOldAged',
    0x000987DE: 'AfricanAmericanOldAged',
    0x000987DF: 'CaucasianOldAged',
}


def fallout_race_edid(race_fid: int):
    """Oblivion race EditorID standing in for an FNV race, else None.

    None for a non-Fallout run or an unmapped id, so the caller keeps its own
    Oblivion lookup and default.
    """
    if not is_fallout_source():
        return None
    name = _FNV_RACE_FID_TO_EDID.get(race_fid & 0x00FFFFFF)
    if not name:
        return None
    for suffix in _FNV_VARIANT_SUFFIXES:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return _FNV_ETHNIC_TO_EDID.get(name)
