# Worldspace extent vs the Havok ±64-cell band — 2026-09-14

Measured with `python tools/validate/cell_grid_check.py <esm> --extents` over
the built plugins in `output/`, plus a static sweep of the GOG/AE
`SkyrimSE.exe`.

## The ±64 bound is a DATA CONSTANT: the Havok broadphase world AABB

**Located.** In the `hkpWorldCinfo` setup function `0x286d10`–`0x2870a2`:

| RVA (.rdata) | Value (havok m) | Game units | Cells | Loaded at |
|---|---|---|---|---|
| `0x1658290` | `3745.38232421875` | **262,144** | **64.000** | `0x286e13` `movaps xmm0` |
| `0x1658280` | `907.0847778320312` | 63,488 | 15.5 | `0x286e1f` `movaps xmm1` |
| `0x1658268` | — | 147,456 | 36.000 | `0x286d94` `movss xmm1` |
| `0x1e429c4` | `3249.9999` | 227,471.56 | 55.535 | `0x286d8a` `movss xmm1` |

Both AABB constants are **broadcast quads** (x,y,z identical, w=0) stored to
stack slots `[rsp+0x50]` / `[rsp+0x40]` that become the `hkpWorldCinfo`
broad-phase world AABB. The scale factor is `0.014287499710917473` havok metres
per game unit (`1/69.9913`), loaded at `0x286d9c`.

**`3745.38232421875` occurs exactly ONCE in the whole executable** (byte-level
displacement search over `.text`, independent of disassembly sync). So does
each of the other three. All four references live in that one function.

`3745.38232421875 × 69.9913 = 262,144.0 = 64 × 4096` exactly. This is the
±64-cell limit, in the one place it exists.

### Why no `cmp` exists (and why earlier searches failed)

Verified absent, so future sessions do not repeat the search:

- No `cmp` against ±64 in the `CellMopp` region (`0x3b42a7`–`0x3b4a90`) or the
  welding worker. Only `sub rsp,0x40` and `and ebx,0xffffff80` (allocator).
- Whole-binary sweep for `cmp r32,0x40` / `cmp r32,-0x40` (imm8 + imm32):
  109 functions hold one, **zero hold both**. A signed range check needs both.
- The welding body `0xa903e1`–`0xa90fed` holds **no cell-scale float and no
  coordinate compare** — only epsilons (1e-5, 0.01, 0.05), FLT_MAX sentinels,
  and small type/state checks.
- No signed-byte packing of cell coordinates anywhere in the chain
  (`movsx`/`movzx` from byte: 2 sites each, all unrelated flag reads).
- `GridCellArray` is sized `uGridsToLoad²` at runtime (`imul eax,eax` at
  `0x1e2032`, min 5, forced odd) — the loaded-cell window, NOT a world bound.

The limit is enforced by Havok's broadphase quantization, not by engine
branching: the broadphase quantizes the world AABB into 16-bit keys, and
objects outside it clamp to `hkpBroadPhaseBorder`. That is why the symptom is a
hard boundary with no branch to patch.

### Patchability — and the test plugin

One constant, one reader: the best possible shape for a patch. Rewriting the
quad is a 16-byte store.

`tes_runtime/havok_world_size/` is an SKSE plugin that does exactly this at
load time, built by `tes_runtime\build.bat` into its own `HavokWorldSize.dll`
and shipped in the TESRuntime archive. Its own source folder and a separate DLL
deliberately: it shares no code with `plugin/` and needs no Address Library, so
a fault in it cannot take TESRuntime down.

It locates the quad **by value**, not by address. Replaying the plugin's own
16-byte-aligned scan against every Skyrim binary on hand finds exactly one site
in each — different addresses, same unique bit pattern:

| Build | `.rdata` size | site | `.text` entropy |
|---|---|---|---|
| SSE GOG/AE | `0x83f276` | `0x1658290` | 6.04 |
| SSE Steam | `0x88308a` | `0x17ab200` | 8.00 (packed) |
| VR, packed | `0x8edbd0` | `0x15de760` | 8.00 (packed) |
| **VR, `SkyrimVR.exe.unpacked.exe`** | `0x8edbd0` | `0x15de760` | **6.05** |

🛑 The VR row was first taken from the PACKED `SkyrimVR.exe`, whose `.text` is
DRM-encrypted. It gave the right answer only because **`.rdata` is not
encrypted** — a data-constant search succeeds identically on a packed binary,
which would have silently hidden an unreadable code section had the target been
an instruction. Always use `SkyrimVR.exe.unpacked.exe`, and check `.text`
entropy before trusting any exe scan.

It exports both `SKSEPlugin_Version` and `SKSEPlugin_Query`, matching
`TESRuntime.dll` — `Query` is what SKSEVR / SKSE 2.0.x use for discovery — so
one DLL covers SE, AE and VR.

VR reports itself as 1.4.15 (read from the binary; its VS_FIXEDFILEINFO
resource is a placeholder `1.0.0.0`), but structurally it tracks GOG 1.6.659:
same parser addresses, open helper, vtable slots and **the 659 stream layout**,
differing only in prologues. See
[asset_convert_creature.md](../commentary/asset_convert_creature.md) for the
measured correspondence.

`fWorldCells` picks the new half-extent; `bDryRun=1` logs the site without
writing.

Cost is broad-phase resolution: the AABB is quantized into 16-bit keys, so the
step is `2 × half_extent / 65536` game units.

| fWorldCells | half-extent (units) | key step | covers |
|---|---|---|---|
| 64 (vanilla) | 262,144 | 8 u | vanilla Skyrim |
| **128** | 524,288 | 16 u | `WrldMorrowind` (worst 116) |
| 256 | 1,048,576 | 32 u | — |
| 512 | 2,097,152 | 64 u | — |

Use the SMALLEST value that covers the worldspace; `TES4Tamriel` (worst 192)
needs 192+.

**CONFIRMED IN-GAME (2026-09-14, `fWorldCells=128`, Steam build.)** The plugin
found and patched exactly one site, and the far-from-origin symptoms resolved.
The broad-phase AABB was the cause.

The by-value search is what made it portable: the Steam `.rdata` is `0x88308a`
where the GOG copy is `0x83f276`, and the quad was still located on the first
try (at `+0x5c200`, with the inner extent at `+0x5c1f0`).

### What the key step actually costs

The quantization bounds broad-phase PAIR BINNING — which pairs reach narrow
phase — not contact accuracy. Contact points, penetration depth and solver
results stay full float32. So the cost is throughput (more candidate pairs per
bin in dense scenes), not correctness.

| fWorldCells | key step | player capsule (34 u) | arrow (40 u) |
|---|---|---|---|
| 64 | 8 u | 4.2 steps | 5.0 |
| 128 | 16 u | 2.1 steps | 2.5 |

Small clutter (~4 u) is already sub-step at vanilla, so nothing changes
category. Unmeasured: Havok sizes internal structures from this AABB, so memory
and broad-phase update cost rise by an unknown amount.

Left deliberately unpatched: the same setup function holds a second size pair
selected by an interior/exterior flag at `0x286d85` (`147456.0` = 36 cells;
`227471.56` = 3250 m). Interiors never approach the limit, so they keep vanilla
resolution.

## Confirmed machinery

| Symbol / string | RVA (GOG/AE) |
|---|---|
| `CellMopp::HeightFieldWeldingTasklet` RTTI | `0x1eaf638` |
| — vtable / inline ctor | `0x1699080` / `0x3b4580` |
| — `Process()` (vfunc[2]) | `0x3b45f0`–`0x3b4673` |
| `CellMopp` vtable / ctor | `0x16990c8` / `0x3b3730` |
| welding worker | `0xa90140` → core `0xa90350`, body `0xa903e1`–`0xa90fed` |
| Havok world setup (`hkpWorldCinfo`) | **`0x286d10`–`0x2870a2`** |
| `bUseCharacterRB:HAVOK` | file offset 25724848 |

Caller chain: `0x277b70` → `0x282280` (allocates `CellMopp`, 0xf0 bytes,
**unconditionally** — no coordinate gate) → `0x3b3730`.

## TWO bugs, not one

**1. Character rigid-body hopping.** Actors sink into and pop out of the
ground past ±64. Cause: landscape MOPP welding tasklets are not queued for
those cells, so `bhkCharacterRigidBody` actors catch on unwelded terrain edges.
Workaround: `[HAVOK] bUseCharacterRB=0` (falls back to the AABB-phantom
`bhkCharacterProxy` controller).

**2. Gameplay interactions break** when the player is past ±64 on either axis
**and facing away from the world origin** — harvestables cannot be picked,
doors cannot be opened, attacks do not land. The ini tweak does NOT fix this.
Beyond Skyrim split provinces into separate worldspaces rather than solve it.
The broadphase-AABB finding above is a plausible single cause for both.

## Measured extents (as built)

| Plugin | Worldspace | Cells | Grid extent | Outside ±64 | Outside ±100 |
|---|---|---|---|---|---|
| Morrowind_ob.esm | `WrldMorrowind` | 10,448 | x[−71,55] y[−44,60] | 110 (1.1%) | 0 |
| TR_Mainland.esm | `WrldMorrowind` | 10,407 | x[−42,99] y[−116,67] | 4,584 (44.0%) | **500** |
| Tamriel_Data.esm | `WrldMorrowind` | 1 | x[−1,−1] y[−1,−1] | 0 | 0 |
| **Union** | `WrldMorrowind` | **18,311** | **x[−71,99] y[−116,67]** | **4,694 (25.6%)** | **500** |
| Tamriel.esp | `TES4Tamriel` | 99,946 | x[−192,191] y[−129,159] | 93,582 (93.6%) | 69,898 |

Morroblivion and TR **share `WrldMorrowind`**, so TR pins the frame for both.

## Recentering helps but cannot fix it

Brute-forced all 281×281 integer shifts, minimizing cells outside ±64:

| Shift | Outside ±64 | worst \|coord\| |
|---|---|---|
| As built (0,0) | 4,694 (25.63%) | 116 |
| Bbox center (−14,+25) | 5,272 (28.79%) | 92 |
| **Optimum (−17,+5)** | **3,645 (19.91%)** | 111 |

Cannot reach zero: the union is 171 × 184 cells against a 128-cell budget. The
two objectives conflict — minimizing cells-outside leaves worst-case 111 (over
the CK's ±100); minimizing worst-case reaches 92 but puts more cells outside.

Morroblivion alone fits (shift (+8,−8), worst 63, zero outside).
`TES4Tamriel` is unreachable by translation (192-cell half-span).

Separate CK limit: exterior cells with |X| or |Y| > 100 are deleted during
"Initializing References" (`cmp eax, 0x64` at `CreationKit.exe+0x1bd3cdf`).

## Ruled out: float precision

float32 ULP at cell 64 is 0.031 units (0.45 mm) and is unchanged through cell
127. Nothing numerical forces a limit at 64. Precision trouble starts near cell
512 (ULP 0.25 units).

| Cell | Units | ULP | mm |
|---|---|---|---|
| 64 | 262,144 | 0.031 | 0.45 |
| 116 | 475,136 | 0.031 | 0.45 |
| 192 | 786,432 | 0.063 | 0.89 |
| 512 | 2,097,152 | 0.25 | 3.6 |

## Status

**Confirmed in-game 2026-09-14** at `fWorldCells=128` on the Steam build: one
site patched, far-from-origin symptoms resolved.

Still unmeasured: memory and frame-time cost of the wider AABB, and whether
`bUseCharacterRB=0` is still needed alongside it (the two fixes were not
isolated from each other).

Addresses above are GOG/AE RVAs and do NOT match Steam — always locate the
constant by value.
