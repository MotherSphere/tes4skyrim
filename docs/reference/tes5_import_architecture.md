# `tes5_import/` architecture — read this BEFORE writing any code here

> **The decision procedure is §3.** If you are about to add or change
> something, start there — it routes any change to exactly one file.

`tes5_import/` reads the TES4 export text and writes a binary TES5 plugin.
**Every TES4→TES5 transformation lives here.** It is not a compiler: it is a
**fan-out over ~65 record signatures** driven by a phase orchestrator, which is
why it is organized by DOMAIN rather than by compiler layer.

---

## 1. The layout

```
tes5_import/
  registry.py     which converter handles which signature
  import_main.py  the orchestrator: reads the export, runs the phases, writes

  base/           the shared floor -- every module here has fan-in >= 4
  generated/      tool output; never hand-edited (see its README)
  record_types/   one converter per TES4 record signature
  dialogue/       DIAL/INFO/QUST, speak-as voices, conversations
  packages/       TES4 PACK -> TES5 package templates
  actors/         races, outfits, faces, hair, idles, footsteps
  overrides/      plugins that have TES4 masters
  navmesh/        PGRD -> NAVM generation
```

### The layer floor

```
L0  registry.py, generated/*, base/{constants, mesh_bounds, equivalents}   stdlib
L1  base/*   (text_reader, writer, tes5_reader, conditions, object_scripts,
              locations, owned_records, ...)                              L0
L1  navmesh/                                                              L0-L1
L2  record_types/*                                                        L0-L1
L3  dialogue/  packages/  actors/        L0-L2, NEVER a sibling L3
L3+ overrides/                           L0-L3 -- it re-runs every converter
L4  import_main.py                       L0-L3+
```

🛑 **An L3 domain may NOT import a sibling L3 domain.** Cross-domain needs go
through `registry.py`, `base/`, or a value the orchestrator passes in.

### Why `base/`, and what belongs in it

Membership is decided by **fan-in**, not by subject. Measured consumer counts:
`text_reader` 34, `writer` 23, `constants` 17, `equivalents` 15,
`object_scripts` 11, `tes5_reader` 5, `conditions` 4, `mesh_bounds` 4.

Two placements look wrong and are not:

- **`base/conditions.py`** (was `dialog_conditions`). CTDA is the **engine-wide**
  condition record, not a dialogue one: `creature_idles` references it 28 times,
  `packages/converter` 25, `record_types/music` 11, plus magic, region and
  world. Its API is byte-level and domain-free. The `dialog_` prefix was the
  only thing that made it look like dialogue.
- **`base/equivalents.py`** (was `skyrim_overrides`). 640 lines of Oblivion →
  Skyrim lookup tables (`RACE_MAP`, `MGEF_CODE_TO_SKYRIM`,
  `TES4_SKILL_TO_TES5_INDEX`, `map_eye_formid`, `resolve_creature_race`). The
  word "overrides" meant master-diffing to every reader; it has nothing to do
  with `overrides/`.

`record_types/` reaches **up** into the domains (`record_types/npc` alone
imports `creature_races`, `hair_variants`, `npc_face_mapper`, `object_scripts`,
`outfits`, `packages`, `equivalents`), which is why the high-fan-in modules sit
in `base/` beneath it.

---

## 2. `registry.py` — why the dispatch table is not in `constants.py`

`constants.py` is DATA. It used to build `IMPORT_DISPATCH` itself, which meant
function-locally importing **17 converter modules** — and 8 of those import
`constants` back at module scope. That is a genuine 8-way cycle, and the
deferred imports were hiding it rather than solving it.

A registry importing its converters is correct direction, so the table moved.
`constants.py` went 275 → 134 code lines with **0** function-local imports.

🛑 **Registration order must stay deterministic.** `load_converters` uses an
explicit import list — never `pkgutil.walk_packages`, whose order depends on
filesystem enumeration. Phase 1 iterates `sorted(simple_types)`, so the table's
order does not reach the output, but do not add a path that would.

---

## 3. The decision procedure

```
0. A new RECORD TYPE?          -> record_types/<kind>.py, registered in
                                  registry.py.  TWO files.
1. A CONDITION (CTDA) rule?    -> base/conditions.py.  It is engine-wide, not
                                  dialogue-specific.
2. An Oblivion -> Skyrim VALUE
   lookup (race, eye, MGEF...)? -> base/equivalents.py
3. Master-diff behaviour?      -> overrides/.  Never a converter.
4. Something TWO domains need? -> base/, registry.py, or a value the
                                  orchestrator passes in.
                                  NEVER a sibling L3 import.
5. A generated table?          -> generated/, and update its generator AND
                                  generated/README.md.
6. NAVMESH GEOMETRY?           -> navmesh/.  Editing anything there changes the
                                  shared cache tag: republish afterwards (§4).
```

---

## 4. Invariants

1. 🛑 **The navmesh cache tag is a SHA-1 over the bytes of
   `tes5_import/navmesh/*.py`** (`navmesh/pool.py:navmesh_geom_cache`), minus
   `pool._TAG_EXCLUDE`. Any edit there invalidates every downloader's cache, so
   **republish** (`tools/navmesh/navmesh_cache.py verify`, then
   `navmesh_cache_hook.py --run`).
   `navmesh/edge_links.py` is excluded from the tag AND the push gate:
   `build_edge_links` stitches portals *after* geometry leaves the cache, so it
   can never invalidate an entry.
2. 🛑 **`base/text_reader.py` has ONE module identity.** It holds module-level
   mutable state (the FormID index offset, injected FormIDs) that
   `navmesh/worker.py` and `base/convert_worker.py` re-seed per subprocess. Two
   import paths would give two copies and desync the workers **silently, only
   under multiprocessing**. Never re-export it.
3. 🛑 **`tes5_import/__init__.py` imports NOTHING.** Importing any leaf runs it,
   so a re-export would drag all 17 converters — and their `core` dependency —
   into a tool that wanted one reader. This broke `tools/validate/*` once.
4. **A module that needs the REPO root must count its own depth.**
   `dirname(dirname(__file__))` reaches the repo root only from the package
   root; from `tes5_import/<pkg>/x.py` it stops at `tes5_import/`. This silently
   made `_pile_mesh_bounds` return None and shipped a guessed death-pile OBND —
   caught by an ESM byte-diff, by no test.
5. **Record insertion order is load-bearing.** Phase 1 is a serial loop because
   a thread pool made companion records (ARMA, aimed-MGEF clones) land in
   completion order and broke byte-reproducibility.
6. **FormIDs are hashed, not counted.** `derive_formid(site, key)` keys on
   AUTHORED data only, so moving or splitting a module cannot move an id.
7. 🛑 <a id="object-scripts-import-is-deferred"></a>**`base/object_scripts.py`
   is imported INSIDE the function body by every `record_types/` converter that
   needs it** — `record_types/common.py`, `items.py` and `world.py`. It is the
   one place the module-scope import rule yields, and the reason is a real
   cycle: `object_scripts` imports `script_convert.pipeline` at module scope,
   which imports `tes5_import.dialogue.converter` and
   `tes5_import.dialogue.unlocks` back. Hoisting the import changes which
   module object wins the cycle, and **the rebuilt ESM stops being
   byte-identical** — measured on Knights.esp, which changed hash with no
   change in size. There is no test for this; only a byte-diff catches it.

---

## 5. Verification

**The acceptance criterion for any restructuring is a byte-identical ESM.**

```bash
python convert.py -f Knights.esp --import-only
sha256sum output/Knights.esp/Knights.esp
```

Hash the manifest and `.seq` too — the manifest records companion pairings a
downstream override pass consumes, so it can drift while the ESM does not.

Fast checks after every edit (~2s):

```bash
python -m pytest tests/test_formid_determinism.py tests/test_navmesh_cache.py \
                 tests/test_code_rules.py tests/test_doc_links.py -q
```

**A passing test suite is not sufficient.** Both defects found during the
package restructure — the death-pile OBND fallback and a `NameError` in a
navmesh worker — passed every test and were caught only by building and
comparing bytes.
