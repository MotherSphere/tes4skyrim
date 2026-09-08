# FO3/FNV actor templates

**Code:** `tes5_import/record_types/actors_falloutnv.py`

## The stub owns nothing

FO3/FNV actors inherit by category. A record carries a `TPLT` naming another
actor and an ACBS `TemplateFlags` word saying which categories come from it —
bit 6 is Model/Animation (`wbTemplateFlags`, wbDefinitionsCommon.pas:7715). A
spawn stub therefore has no MODL, no NIFZ, no race and no stats of its own.

`FalloutNV.esm` CREA `00156782` `VSpawnTier3GiantRadscorpionMed` is the whole
pattern in one record: EDID / OBND / EAMT / NIFT / ACBS / TPLT / AIDT / PKID ×2
/ DATA / RNAM / ZNAM / PNAM / TNAM / BNAM / WNAM / NAM4 / NAM5, TemplateFlags
`0x01DF` (Traits, Stats, Factions, Spell List, AI Data, **Model/Animation**,
Base Data, Inventory). Its mesh is two links away:

    00156782  (stub)      TPLT ─▶ 001567A0  LVLC VEncTier3GiantRadscorpionMed
    001567A0  Entry[0]         ─▶ 0014F401  CREA VCrTier3GiantRadscorpionMed
    0014F401             TPLT ─▶ 0001CF9E  CREA CrRadscorpion2Large
                                            MODL Creatures\Radscorpion\Skeleton.nif

So the chain passes through a leveled list, which is why the resolver follows
`Entry[i].FormID` as well as `TPLT.Template`.

## Why this became a Skyrim giant

`convert_CREA` picks a race in two steps: `get_creature_race(fid)` for a
generated creature race, else `resolve_creature_race(edid, full)`, which
keyword-matches the EditorID. A modelless stub gets no folder, so
`build_creature_races` never registers it and the first step returns None. The
second then matched the substring `giant` in `VSpawnTier3GiantRadscorpionMed`
and returned Skyrim's `GiantRace` (0x000131F9, `skyrim_overrides.py:186`).

The radscorpion's own race, meshes and animations were built correctly and sat
unused. Only the pointer from the placed spawn to that creature was missing —
first because `tes4_export` never emitted TPLT at all
([the export side](tes4_export_falloutnv.md#tplt-carries-the-whole-actor)), and
then because nothing here consumed it.

## Flatten rather than walk

Every pass in this package reads a CREA's own `Model.MODL`: the creature-race
builder derives the folder from it, the body-set lookup keys off `NIFZ`, and
creature voices key off the folder. Teaching each of them to walk a template
chain would be the same fix repeated in several places, and each would have to
agree about depth limits and cycles.

Copying the inherited model onto the stub once, before any of them run, fixes
all of them with no other change — the stub then looks like an ordinary actor
that happens to share a mesh with its template, which is what it is. Only the
categories the flags actually claim are copied, so a stub that overrides its
own model keeps it.

The engine still resolves the remaining categories through TPLT at spawn time,
exactly as `tes5_import/leveled_actors.py` relies on for Oblivion's placed-LVLC
shells; flattening the model does not change that contract.
