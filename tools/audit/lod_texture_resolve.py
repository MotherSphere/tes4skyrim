"""Textures named by baked LOD tiles that resolve NOWHERE -- the purple test.

A tile embeds geometry and names its textures by path. If a named texture is
in neither our own output nor vanilla Skyrim, the game renders it purple. This
is the only check that proves "no purple LOD": a per-defect check can pass
while a tile still names something nothing provides.

Vanilla MUST be consulted. A bare unprefixed path (`white.dds`,
`default_n.dds`) is usually a legitimate stock-asset reference, not a defect,
so an output-only check reports false purples.

  python tools/audit/lod_texture_resolve.py                 # every tile
  python tools/audit/lod_texture_resolve.py --lod-dir D     # one bake
  python tools/audit/lod_texture_resolve.py --show 40
"""
import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.worker_budget import worker_count

#: A texture path is a WHOLE NUL-delimited run, never a slice of one.
_TEX_RE = re.compile(rb'\A[\w\\/][\w\\/. -]{2,180}\.dds\Z', re.IGNORECASE)

#: Bethesda strings sit between NULs; runs are split on this.
_NUL = bytes([0])

#: Read tiles in chunks: a whole .bto is large enough to exhaust memory.
_CHUNK = 4 << 20
_OVERLAP = 512


def tile_textures(path: Path) -> set:
    """Every .dds path named by one baked tile.

    Each candidate must be a COMPLETE NUL-delimited run. Matching a substring
    of the raw buffer instead lets a match begin inside binary float data and
    run forward into a following string, inventing refs nothing ever named --
    `JEYE.Dds` and `default.dds` were both float bytes glued to a real path's
    tail, and both were reported as purple.
    """
    out, tail = set(), b''
    with open(path, 'rb') as fh:
        while True:
            buf = fh.read(_CHUNK)
            if not buf:
                break
            for run in (tail + buf).split(_NUL):
                if _TEX_RE.match(run):
                    out.add(run.decode('ascii', 'replace').lower())
            tail = buf[-_OVERLAP:]
    return out


def norm_ref(rel: str) -> str:
    """A texture ref reduced to its path below the textures root.

    Tiles name terrain textures `data\\textures\\terrain\\...` while object
    refs are already relative, so both prefixes are stripped before comparing.
    Missing this reports every terrain tile as purple -- 3,952 false positives.
    """
    out = str(rel).replace('/', '\\').lower().lstrip('\\')
    for prefix in ('data\\', 'textures\\'):
        if out.startswith(prefix):
            out = out[len(prefix):]
    return out


def output_textures(out_root: Path) -> set:
    """Every texture path our own build ships, relative to a textures root."""
    have = set()
    for plugin in sorted(p for p in out_root.iterdir() if p.is_dir()):
        tex = plugin / 'textures'
        if not tex.is_dir():
            continue
        for dirpath, _d, files in os.walk(tex):
            rel = Path(dirpath).relative_to(tex)
            for f in files:
                if f.lower().endswith('.dds'):
                    have.add(norm_ref(str(rel / f)))
    return have


def resolves_in_vanilla(rel: str) -> bool:
    """Whether stock Skyrim provides this texture."""
    from asset_convert.sources.skyrim_assets import get_asset_bytes
    for cand in (rel, 'textures\\' + rel):
        try:
            if get_asset_bytes(cand):
                return True
        except Exception:
            continue
    return False


def scan_tiles(lod_dir: Path, workers: int = 0) -> set:
    """Every distinct texture ref across every baked tile under `lod_dir`.

    Tiles total over a gigabyte, so the scan runs parallel and streams progress
    -- a single-threaded pass does not finish inside a sane timeout.
    """
    tiles = sorted(list(lod_dir.rglob('*.bto')) + list(lod_dir.rglob('*.btr')))
    total = sum(t.stat().st_size for t in tiles)
    print(f'tiles: {len(tiles)} ({total / 1e9:.2f} GB)', flush=True)
    named = set()
    with ProcessPoolExecutor(max_workers=workers or worker_count()) as ex:
        for i, got in enumerate(ex.map(tile_textures, tiles, chunksize=4), 1):
            named |= got
            if i % 200 == 0 or i == len(tiles):
                print(f'  {i}/{len(tiles)} tiles, {len(named)} refs',
                      flush=True)
    return named


def main(argv=None) -> int:
    """Report tile texture refs resolving in neither output/ nor vanilla."""
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lod-dir', default=None,
                    help='bake root (default: output/AutoConvertLOD)')
    ap.add_argument('--output-dir', default=None)
    ap.add_argument('--show', type=int, default=25)
    ap.add_argument('--workers', type=int, default=0)
    args = ap.parse_args(argv)

    out_root = Path(args.output_dir or ROOT / 'output')
    lod_dir = Path(args.lod_dir or out_root / 'AutoConvertLOD')
    if not lod_dir.is_dir():
        raise SystemExit(f'no LOD bake at {lod_dir}')

    named = scan_tiles(lod_dir, args.workers)
    print(f'distinct texture refs: {len(named)}')

    have = output_textures(out_root)
    print(f'textures in output/: {len(have)}')

    missing = sorted({norm_ref(r) for r in named} - have)
    print(f'not in output/: {len(missing)}  (checking vanilla...)')

    purple, vanilla = [], []
    for rel in missing:
        (vanilla if resolves_in_vanilla(rel) else purple).append(rel)

    print(f'\nresolved by vanilla Skyrim : {len(vanilla)}')
    for r in vanilla[:args.show]:
        print(f'    {r}')
    print(f'\nTRUE PURPLE (nowhere)      : {len(purple)}')
    for r in purple[:args.show]:
        print(f'    {r}')
    print('\nVERDICT:', 'NO PURPLE' if not purple else f'{len(purple)} PURPLE')
    return 1 if purple else 0


if __name__ == '__main__':
    sys.exit(main())
