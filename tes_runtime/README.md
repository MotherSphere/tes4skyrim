# TESRuntime

The converter's SKSE plugin. One job, done on engine contracts measured in
`SkyrimSE.exe` and resolved through the Address Library or a signature scan
(no raw RVAs): **animation cache composition**. The converter writes one
fragment per plugin (`SKSE\Plugins\TESRuntime\animation\<plugin>.json`) and
this DLL composes `vanilla base + every fragment` in memory when the engine
parses `animationdatasinglefile.txt` / `animationsetdatasinglefile.txt`.
Schema and rules: [docs/reference/tes_runtime_fragments.md](../docs/reference/tes_runtime_fragments.md);
why, and the engine facts per build (1.6.659, 1.6.1170, Skyrim VR):
[docs/commentary/asset_convert_creature.md#runtime-animation-cache-composition](../docs/commentary/asset_convert_creature.md#runtime-animation-cache-composition).

`TESRuntime.dll` is committed prebuilt so an end user never compiles anything;
rebuild it with `build.bat` (MSVC x64 only) after changing `plugin/`. It
resolves three addresses and touches no form, native or co-save. Both
`SKSEPlugin_Version` (AE SKSE) and `SKSEPlugin_Query` (SE 1.5.97 SKSE,
SKSEVR) are exported.

Verify the version struct landed in `.data` with
`python tools/misc/skse_version_data.py tes_runtime/TESRuntime.dll`.
`compose_test.exe <base_dir> <fragment_dir> <out_dir>` runs the composer
offline; `tests/test_creature_anim.py` diffs it against the Python reference.

Package it for install with the GUI's **Pack SKSE Mod** button
(`tools/release/package_runtime_dll.py`). Log:
`Documents\My Games\Skyrim Special Edition\SKSE\TESRuntime.log`, with the
composed text beside it as `TESRuntime_composed_*.txt`.
