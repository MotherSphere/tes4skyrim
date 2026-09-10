# hkxconv — Skyrim SE 64-bit Havok packfile ↔ XML

```
hkxconv toxml <in.hkx> <out.xml>    packfile (either bitness) -> XML
hkxconv tohkx <in.xml> <out.hkx>    XML -> SSE 64-bit packfile
```

A thin command line over Monitor221hz's HKX2-Enhanced-Library: a ~60-line
`Program.cs` that opens, deserializes, serializes and writes. Only the built
binary is committed — the source and the library are cloned into untracked
`references/` when someone needs to rebuild (below).

## Why it exists

`hkxcmd` is 32-bit Havok 2010 and **cannot read a 64-bit packfile at all**: it
answers `File is not loadable` on vanilla `0_master.hkx` for every output
format, `-v:WIN32` included, so it cannot be used to narrow a file to 32-bit
first either. Bitness is a property of its deserializer, not of a conversion
pass. The LE copies of the humanoid behavior graphs predate Dawnguard, so they
are not a substitute source.

The FNV gun work patches Bethesda's own shipped SSE graphs in place — the
humanoid project is one set shared by every race, so new weapon states cannot
ship as a standalone project the way a creature's can. Reading those files is
the one job this binary does. It replaces nothing: `hkxcmd` remains the only
option for `CONVERTKF` and for generating hk_2010 creature assets, and HKX2E
knows only Skyrim SE classes.

See: [asset_convert_falloutnv.md#gun-graph](../../docs/commentary/asset_convert_falloutnv.md#gun-graph)

## Rebuilding

The shipped `hkxconv.exe` is self-contained (no .NET runtime needed on the
user's machine) and trimmed, 12.1 MB. It is committed; you only need this if
you change the wrapper or update the library.

The build happens entirely under untracked `references/`, so no build artifact
ever lands in the tracked tree. `references/hkxconv/` holds `Program.cs`,
`hkxconv.csproj` and `roots.xml`; the library is a sibling clone.

```bash
git clone https://github.com/Monitor221hz/HKX2-Enhanced-Library references/HKX2-Enhanced-Library
dotnet publish references/hkxconv/hkxconv.csproj -c Release \
    -p:HKX2E=<abs path>/HKX2-Enhanced-Library/HKX2/HKX2E.csproj \
    -o external/hkxconv
rm -f external/hkxconv/HKX2E.pdb        # the referenced project drops this
```

Needs the **.NET 10 SDK**. The library path is passed in rather than hardcoded,
so the clone can live anywhere; `bin/` and `obj/` land beside the csproj in
`references/`. `external/hkxconv/` holds only the exe and this README.

`roots.xml` is required and must not be dropped: HKX2E resolves every Havok
class by string name (`Type.GetType("HKX2E." + hkClassName)` then
`Activator.CreateInstance`), which the trimmer cannot see. Without the root the
build still succeeds and is the same size, then fails at runtime with
`MissingMethodException` on `hkRootLevelContainer`.

Measured alternatives, all rejected: untrimmed self-contained 38 MB;
framework-dependent 2.0 MB but needs a .NET runtime installed, which end users
will not have; NativeAOT 13.0-13.4 MB — larger *and* broken, dying on
`Reflection_InsufficientMetadata` for reflectively-reached types.

Verified after any rebuild — `toxml` then `tohkx` returns the original byte
size, for all four graphs the gun patch touches:

| file | bytes |
|---|---|
| `0_master.hkx` | 580,896 |
| `1hm_behavior.hkx` | 1,213,808 |
| `weapequip.hkx` | 63,616 |
| `1hm_locomotion.hkx` | 165,600 |

## Upstream caveat

HKX2-Enhanced-Library's README lists XML→HKX as **not** supported ("~XML to
HKX~ use figment/hkxcmd"). `tohkx` uses `HavokXmlDeserializer` +
`PackFileSerializer` for exactly that, and it round-trips byte-size-identically
on every graph above — but it is a path upstream does not claim, so an update
to the library could break it silently.

## Attribution

`src/Program.cs` (this project, MIT) is the only original code here. The binary
statically links the library chain below, all of it third-party:

| Component | Role |
|---|---|
| [Monitor221hz — HKX2-Enhanced-Library](https://github.com/Monitor221hz/HKX2-Enhanced-Library) | The packfile (de)serializer this wraps; a fork of ret2end's HKX2 for packfile *editing* |
| [ret2end — HKX2Library](https://github.com/ret2end/HKX2Library) | The Skyrim SE HKX2 library it forks |
| [katalash — HKX2 / DSMapStudio](https://github.com/katalash/DSMapStudio) | The original HKX2 library |
| [krenyy — HKX2Library](https://gitlab.com/HKX2/HKX2Library) | HKX2 library |
| [JKAnderson — SoulsFormats](https://github.com/JKAnderson/SoulsFormats) | `BinaryReaderEx` / `BinaryWriterEx` |
| [Dexesttp — hkxpack](https://github.com/Dexesttp/hkxpack/tree/main/doc/hkx%20findings) | HKX format research |

**No upstream repo in that chain states a license.** HKX2-Enhanced-Library has
no LICENSE file; it is a community project distributed publicly and forked
freely. The binary is redistributed here on that basis. It carries no Havok SDK
code — HKX2E is a clean-room reimplementation working from dumped class
layouts, unlike `hkxcmd` and the mopp bridge, which statically link Havok.
