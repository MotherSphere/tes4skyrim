# TESRuntime

The converter's SKSE plugin. Three jobs (gun routing, `guns.cpp`, is the third:
[docs/commentary/asset_convert_falloutnv.md#gun-graph](../docs/commentary/asset_convert_falloutnv.md#gun-graph)),
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
