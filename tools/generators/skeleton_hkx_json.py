"""Dump a vanilla Skyrim skeleton hkx's hkaSkeleton to the retarget JSON.

The gun retarget (`clip_retarget.Skeleton.from_hkx_json`) needs the humanoid
rig in the hkx's own bone ORDER, which the skeleton.nif does not give. Reads
the packfile through skyrim_assets + hkxconv and writes one entry per bone:
name, parent, translation, quat_xyzw, scale, lock.

    python tools/generators/skeleton_hkx_json.py            # both rigs
    python tools/generators/skeleton_hkx_json.py --rel <data path> --out f.json
See: docs/commentary/asset_convert_falloutnv.md#first-person-rig
"""

import argparse
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), '..'))

from asset_convert import paths
from asset_convert.havok.humanoid_graph import hkxconv
from asset_convert.sources.skyrim_assets import get_asset_bytes

GENERATED = paths.REPO / 'asset_convert' / 'generated'
#: (data-relative packfile, output name) of the rigs the gun retarget targets.
RIGS = (('meshes\\actors\\character\\character assets\\skeleton.hkx',
         'skeleton_hkx_skyrim_male.json'),
        ('meshes\\actors\\character\\_1stperson\\characterassets'
         '\\skeletonFirst.hkx', 'skeleton_hkx_skyrim_1stperson.json'))
_TRIPLE = re.compile(r'\(([^)]*)\)\s*\(([^)]*)\)\s*\(([^)]*)\)')


def _param(text: str, name: str) -> str:
    """The body of the first `<hkparam name=...>` called `name`."""
    m = re.search(rf'<hkparam name="{name}"[^>]*>(.*?)</hkparam>', text, re.S)
    if m is None:
        raise ValueError(f'no hkparam {name}')
    return m.group(1)


def skeleton_json(hkx_bytes: bytes) -> dict:
    """{'name', 'bones': [...]} for the first hkaSkeleton in the packfile."""
    with tempfile.TemporaryDirectory() as td:
        hkx, xml = os.path.join(td, 'in.hkx'), os.path.join(td, 'in.xml')
        with open(hkx, 'wb') as f:
            f.write(hkx_bytes)
        hkxconv('toxml', hkx, xml)
        with open(xml, encoding='utf-8') as f:
            text = f.read()
    text = text[text.index('class="hkaSkeleton"'):]
    parents = [int(v) for v in _param(text, 'parentIndices').split()]
    bones = re.findall(r'<hkobject>\s*<hkparam name="name">([^<]*)</hkparam>'
                       r'\s*<hkparam name="lockTranslation">([^<]*)</hkparam>',
                       text[:text.index('<hkparam name="referencePose"')])
    pose = _TRIPLE.findall(_param(text, 'referencePose'))
    if not len(parents) == len(bones) == len(pose):
        raise ValueError(f'{len(parents)} parents, {len(bones)} bones, '
                         f'{len(pose)} poses')
    out = []
    for (name, lock), parent, (t, q, s) in zip(bones, parents, pose):
        out.append({'name': name, 'parent': parent,
                    'translation': [float(v) for v in t.split()],
                    'quat_xyzw': [float(v) for v in q.split()],
                    'scale': float(s.split()[0]), 'lock': lock == 'true'})
    return {'name': _param(text, 'name'), 'bones': out}


def write_rig(rel: str, out_path: str) -> int:
    """Dump `rel` to `out_path`; the bone count."""
    raw = get_asset_bytes(rel)
    if raw is None:
        raise FileNotFoundError(rel)
    data = skeleton_json(raw)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1)
    return len(data['bones'])


def main():
    """Dump the rigs named on the command line, or both humanoid rigs."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rel', help='data-relative skeleton hkx')
    ap.add_argument('--out', help='output json (with --rel)')
    args = ap.parse_args()
    rigs = [(args.rel, args.out)] if args.rel else [
        (rel, str(GENERATED / name)) for rel, name in RIGS]
    for rel, out in rigs:
        print(f'{rel} -> {out}: {write_rig(rel, out)} bones')


if __name__ == '__main__':
    main()
