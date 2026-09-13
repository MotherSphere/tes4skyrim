# asset_convert/sources/bsa_pack.py — BSA packing

**Code:** `asset_convert/sources/bsa_pack.py`

## Contents

- [Staging past the Windows path limit](#staging-past-the-path-limit)

## Staging past the Windows path limit
<a id="staging-past-the-path-limit"></a>

**Code:** `long_path` in `asset_convert/sources/bsa_pack.py`

Each archive is staged into `output/<plugin>/_bsa_staging_<type>/` as a tree of
hardlinks, and BSArch is pointed at that root. The staged path is therefore
longer than the source path it mirrors, by the whole
`_bsa_staging_<type>\` segment.

For a plugin with a long folder name that is enough to cross Windows'
260-character `MAX_PATH`. Measured over the 15 plugins in `output/`, the
longest staged paths are:

```
_bsa_staging_misc = 266   Unique Landscapes Compilation v2.2.0   <-- FAILS
                    228   Oblivion.esm, Nehrim.esm
                    215   Morrowind_ob.esm
```

Only creature animdata reaches these lengths -- the offender is
`meshes\animationsetdata\tes4<plugin>_clear stream fishprojectData\
tes4<plugin>_clear stream fishproject.txt`, where the plugin name appears
TWICE below the staging root.

The failure is badly disguised. Under `-mt` BSArch reports only
`EAggregateException: One or more errors occurred` with no path, and the
pipeline truncates its output at 200 characters, so the message that reaches
the log is the tool's copyright banner. Dropping `-mt` produces the real
diagnosis: `"...evilspritecharacter.hkx". The system cannot find the path
specified`. The file is present; the path is simply too long to open.

`long_path` prefixes `\\?\`, which raises the limit to ~32,767 characters. It
is applied in two places, and both are needed:

1. `_link_or_copy`, so `os.link` can CREATE the staged path.
2. BSArch's INPUT root, so BSArch can WALK it.

Measured against a synthetic 381-character staging tree:

| input | output | result |
|---|---|---|
| plain | plain | `EAggregateException` |
| `\\?\` | plain | **159.2 MB packed** |
| plain | `\\?\` | `EAggregateException` |
| `\\?\` | `\\?\` | 159.2 MB packed |

Only the input root matters -- the archive being written sits directly in the
plugin dir and is never near the limit -- but prefixing both is harmless and
leaves nothing to rediscover.

The prefix is Windows-only and requires a normalized absolute path: `\\?\`
disables all path parsing, so a `/` separator or a `..` segment inside one is
passed through to the filesystem verbatim and fails. `long_path` returns its
argument unchanged off Windows, on a relative path, and on a path that already
carries the prefix.

### Why not just shorten the staging directory

`_bsa_misc` clears the limit by 2 characters and `_bsm` by 7, against a path
whose length the USER controls through both the repo location and the plugin
folder name. That is a reprieve, not a fix: the next long plugin name fails
again, and the failure mode is the disguised one above.
