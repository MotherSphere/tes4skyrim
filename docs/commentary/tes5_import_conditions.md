# tes5_import/base/conditions.py — CTDA translation

**Code:** `tes5_import/base/conditions.py`

CTDA is Bethesda's engine-wide condition record, not a dialogue one: it is read
by `creature_idles`, `packages/converter`, `record_types/music`, magic, region
and world. The translation service lives in `base/` for that reason.

Parameter remapping and the crash rule are in
[package_ai_contracts.md](../reference/package_ai_contracts.md#ctda-parameter-remapping--the-crash-rule).

## Contents

- [Actor-value indices diverge from the BOOK skill table](#actor-value-vs-book-skill-table)
- [Chargen-identity conditions become menu-choice globals](#chargen-identity-to-menu-globals)
- [Speak-as topics drop the actor-interrogating conditions](#non-actor-speaker-drop)

## <a id="chargen-identity-to-menu-globals"></a>Chargen-identity conditions become menu-choice globals

`CHARGEN_CHOICE` maps a TES4 function index to
`(choice GLOB output FormID, {param fid24 -> menu index})`.

Two TES4 chargen conditions cannot survive as themselves:
`GetIsPlayerBirthsign` (224) is **dead in Skyrim** — that index is reused for
`GetVATSMode` — and `GetPCIsClass` (129) **can never be true**, because the
player never has a TES4 CLAS.

The converted `ShowBirthsignMenu` / `ShowClassMenu` write the picked menu index
+ 1 into a GLOB (0 = not chosen), so these conditions become
`GetGlobalValue(<choice>) ==/!= index+1`.

**Why it matters:** the Emperor's "Your stars are not mine. Today the
&lt;sign&gt;…" lines are **13 INFOs each gated on one sign**. Without this
translation the first INFO always won regardless of what the player picked.

The table is populated per plugin by the import pipeline and is empty when the
plugin ships no BSGN/CLAS records — 224 then falls through to `_FUNC_DROP` as
before.

## <a id="non-actor-speaker-drop"></a>Speak-as topics drop the actor-interrogating conditions

`NON_ACTOR_SPEAKER_DROP` lists conditions that interrogate the SPEAKER as an
actor. A speak-as topic is spoken by a **non-actor reference**, which has no
base NPC, no voice type and no race, so each of these is unsatisfiable there —
and only there.

| Index | Function | Why it cannot pass |
|---|---|---|
| 72 | `GetIsID` | compares the speaker's base form |
| 254 | `GetIsPlayableRace` | rides in from the QUST-level condition copy |

## <a id="actor-value-vs-book-skill-table"></a>Actor-value indices diverge from the BOOK skill table

`_TES4_AV_TO_TES5` maps a TES4 actor-value index to its TES5 index. Skills
mostly follow `base.equivalents.TES4_SKILL_TO_TES5_INDEX`, but **two entries
deliberately differ**, because the two tables answer different questions: the
BOOK table must name a real *trainable* skill, while a CONDITION only has to
read a comparable number.

| TES4 value | BOOK table | Condition table | Why |
|---|---|---|---|
| Mercantile | Pickpocket | **Speech (17)** | Mercantile is Oblivion's haggling skill and Speech is Skyrim's. Pickpocket appears in the BOOK table only because Skyrim already ships a Speech skill book for that slot. |
| Athletics, Acrobatics | — | **Stamina (26)** | Neither has a Skyrim skill at all; Stamina is the athletic-capacity value the engine actually tracks. |

Changing either to match the BOOK table would make the condition read a value
the actor never trains, so it would compare against a constant.
