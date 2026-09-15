# TESRuntime

The converter's SKSE plugin. Four jobs (gun routing, `guns.cpp`, is the third:
[docs/commentary/asset_convert_falloutnv.md#gun-graph](../docs/commentary/asset_convert_falloutnv.md#gun-graph);
the gun shot, reload key and ammo restriction, `fire.cpp`, the fourth:
[docs/commentary/tes_runtime_guns.md](../docs/commentary/tes_runtime_guns.md)),
all done on engine contracts measured
in `SkyrimSE.exe` and resolved through the Address Library (no raw RVAs):

1. **Animation cache composition.** The converter writes one fragment per
   plugin (`SKSE\Plugins\TESRuntime\animation\<plugin>.json`) and this DLL composes
   `vanilla base + every fragment` in memory when the engine parses
   `animationdatasinglefile.txt` / `animationsetdatasinglefile.txt`.
   Schema and rules: [docs/reference/tes_runtime_fragments.md](../docs/reference/tes_runtime_fragments.md);
   why: [docs/commentary/asset_convert_creature.md#runtime-animation-cache-composition](../docs/commentary/asset_convert_creature.md#runtime-animation-cache-composition).
2. **FO3/FNV limb severing.** On a fatal projectile hit the DLL hides the
   struck limb's FO3-numbered partitions and reveals its gore caps, from the
   sidecars the importer writes to `SKSE\Plugins\TESRuntime\`:
   [docs/commentary/asset_convert_falloutnv.md#dismemberment](../docs/commentary/asset_convert_falloutnv.md#dismemberment).

## HavokWorldSize.dll

Source in `havok_world_size/`. Built by the same `build.bat` and packaged in
the same archive, but its own source folder and a **separate DLL** — it shares
no code with `plugin/` and needs no Address Library, so a fault in it cannot
take TESRuntime down.

It widens Skyrim's Havok broad-phase world AABB past its vanilla ±64 cells,
which is what breaks physics and interactions far from the world origin. The
limit is a single `.rdata` float (`3745.38232421875` havok m = 262,144 game
units = 64 × 4096) that the `hkpWorldCinfo` setup loads as the broad-phase
extent; objects outside it clamp to `hkpBroadPhaseBorder`.

It finds that constant **by value** (a 16-byte-aligned broadcast quad), not by
address, so no Address Library is needed and no build is hardcoded — verified
to occur exactly once in SSE GOG/AE, SSE Steam and the **unpacked** Skyrim VR
binary. Exports `SKSEPlugin_Query` as well as `SKSEPlugin_Version`, matching
TESRuntime, so one DLL is discoverable on SE, AE and VR.

`HavokWorldSize.ini` sets `fWorldCells` (default 128; use the SMALLEST value
covering your worldspace — the broad-phase key step doubles with it) and
`bDryRun=1` to log the site without writing. Log:
`Documents\My Games\Skyrim Special Edition\SKSE\HavokWorldSize.log`.
Runtime-only: no record data, no FormIDs, so removing it fully reverts.
Analysis: [docs/audits/worldspace_havok_range.md](../docs/audits/worldspace_havok_range.md).

## Building

Build with `build.bat` (MSVC x64 only). `build.bat cache-only` builds
`TESRuntime_CacheOnly.dll` instead: job 1 alone, with `engine.cpp`, `guns.cpp`
and `sever.cpp` not compiled in, so the cache composition can be tested with
nothing else patched into the game. It resolves three Address Library ids and
touches no form, native or co-save; it registers as `TESRuntimeCacheOnly` and
logs to `TESRuntimeCacheOnly.log`, so it never collides with the full plugin.
Install one or the other, never both.

Verify the version struct landed in
`.data` with `python tools/misc/skse_version_data.py tes_runtime/TESRuntime.dll`.
`compose_test.exe <base_dir> <fragment_dir> <out_dir>` runs the composer
offline; `tests/test_creature_anim.py` diffs it against the Python reference.

The converter copies `TESRuntime.dll` into `output\<plugin>\SKSE\Plugins\`
whenever a plugin generates a creature project. Log:
`Documents\My Games\Skyrim Special Edition\SKSE\TESRuntime.log`.
