"""Gather real Havok collision for a Beyond Skyrim: Bruma cell.

The transplant editor places pathgrid nodes against Bruma's ACTUAL walls, not
against the authored navmesh outline -- placing nodes by eyeballing the answer
key is exactly the leak the corpus exists to avoid.  That needs the same
collision soup the Oblivion-side renders use, built the same way.

Bruma ships its meshes inside the two `- Textures.bsa` archives; the plain
`BSHeartland.bsa` / `BSAssets.bsa` hold only sound, voice and scripts.  Cells
also place vanilla Skyrim statics, which fall back to `skyrim_assets`.

    python tools/navmesh/bruma_collision.py CYRBrumaChapelHall

See: docs/commentary/tes5_import_navmesh.md#bruma-collision
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np

from asset_convert.collision import collision_extract as ce
from asset_convert.nif.sse_nif import read_nif
from asset_convert.sources.bsa_extract import read_bsa_files
from asset_convert.sources.skyrim_assets import get_asset_bytes
from tes5_import.base.tes5_reader import subrecords, walk
from tes5_import.navmesh.world import place, rot_matrix

#: Default Vortex staging root; `stagingPath` in Data/vortex.deployment.json.
STAGING = r'C:\Other Games\Mod Staging\skyrimse'

#: Vanilla LE meshes; these parse where their SSE twins hit pyffi bugs.
LE_MESHES = os.path.join('references', 'Skyrim Meshes', 'meshes')

#: Archives that actually carry meshes, in load order.
MESH_BSAS = (
    ('Beyond Skyrim - Bruma-10917-1-5-2-1639253787',
     'BSHeartland - Textures.bsa'),
    ('Beyond Skyrim - Assets-10917-1-5-2-1639253786',
     'BSAssets - Textures.bsa'),
)

#: Base record types whose MODL is worth placing as collision.
_MODEL_SIGS = (b'STAT', b'FURN', b'DOOR', b'MSTT', b'ACTI', b'CONT',
               b'LIGH', b'TREE', b'FLOR')

_SEP = chr(92)


def _read(path):
    """`(bytes, span start)` for an ESM, skipping its header record."""
    with open(path, 'rb') as fh:
        data = fh.read()
    return data, 24 + struct.unpack_from('<I', data, 4)[0]


def _edid(body):
    """The record's EditorID, or ''."""
    for tag, s in subrecords(body):
        if tag == b'EDID':
            return s.rstrip(b'\0').decode('latin1')
    return ''


def _modl(body):
    """The record's MODL path, or None."""
    for tag, s in subrecords(body):
        if tag == b'MODL':
            return s.rstrip(b'\0').decode('latin1')
    return None


def _placement(body):
    """`(base FormID, pos, rot, scale)` from a REFR body, or None."""
    base = pos = rot = None
    scale = 1.0
    for tag, s in subrecords(body):
        if tag == b'NAME':
            base = struct.unpack_from('<I', s, 0)[0]
        elif tag == b'DATA' and len(s) >= 24:
            v = struct.unpack_from('<6f', s, 0)
            pos, rot = v[:3], v[3:]
        elif tag == b'XSCL' and len(s) >= 4:
            scale = struct.unpack_from('<f', s, 0)[0]
    if base is None or pos is None:
        return None
    return base, pos, rot, scale


def cell_refrs(esm, cell_name):
    """`(models, refrs)`: base FormID -> MODL, and this cell's placements."""
    data, start = _read(esm)
    target = None
    models = {}
    want = cell_name.lower()
    for rec, _st in walk(data, span=(start, len(data))):
        if rec.sig == b'CELL' and _edid(rec.body).lower() == want:
            target = rec.form_id
        elif rec.sig in _MODEL_SIGS:
            m = _modl(rec.body)
            if m:
                models[rec.form_id] = m
    if target is None:
        return {}, []
    refrs = []
    for rec, st in walk(data, span=(start, len(data))):
        if rec.sig == b'REFR' and st.cell == target:
            p = _placement(rec.body)
            if p is not None:
                refrs.append(p)
    return models, refrs


def _bsa_paths(staging):
    """Existing mesh-bearing archive paths, in load order."""
    out = []
    for mod, bsa in MESH_BSAS:
        p = os.path.join(staging, mod, bsa)
        if os.path.isfile(p):
            out.append(p)
    return out


def _le_reference(rel):
    """Bytes of a vanilla mesh from the LE reference tree, or None.

    See: docs/commentary/tes5_import_navmesh.md#le-references-beat-sse-bsas
    """
    p = os.path.join(LE_MESHES, rel.replace('/', _SEP))
    if not os.path.isfile(p):
        return None
    with open(p, 'rb') as fh:
        return fh.read()


def _fetch_blobs(model_paths, staging):
    """`{model path: nif bytes}`: Bruma, then LE references, then SSE BSAs."""
    want = {('meshes' + _SEP + m).lower().replace('/', _SEP): m
            for m in model_paths}
    blobs = {}
    for bsa in _bsa_paths(staging):
        for k, v in read_bsa_files(bsa, list(want.keys())).items():
            m = want.get(k.lower().replace('/', _SEP))
            if m and m not in blobs:
                blobs[m] = v
    for m in model_paths:
        if m in blobs:
            continue
        data = _le_reference(m)
        if data is None:
            try:
                data = get_asset_bytes('meshes' + _SEP + m)
            except Exception:
                data = None
        if data:
            blobs[m] = data
    return blobs


def load_collision_soups(model_paths, staging, quiet=True):
    """`{model path: (walkable_flat, blocking_flat)}` for the paths given.

    Parsed via `sse_nif.read_nif`, which supplies the SSE read layouts: vanilla
    Skyrim clutter placed in Bruma cells is BSTriShape-format, which pyffi
    alone misparses.
    """
    blobs = _fetch_blobs(model_paths, staging)
    if not quiet:
        missing = [m for m in model_paths if m not in blobs]
        print('  %d/%d models found%s' % (len(blobs), len(model_paths),
                                          '' if not missing else
                                          ', missing e.g. ' + missing[0]))
    out = {}
    for m, blob in blobs.items():
        try:
            col = ce.collision_from_data(read_nif(blob))
        except Exception as exc:
            if not quiet:
                print('  collision failed for %s: %s' % (m, exc))
            col = None
        out[m] = (col.get('w'), col.get('b')) if col else (None, None)
    return out


def cell_collision(esm, cell_name, staging=STAGING, quiet=True):
    """`(walkable, blocking)` world-space (N,3,3) arrays for a Bruma cell."""
    models, refrs = cell_refrs(esm, cell_name)
    used = sorted({models[b] for (b, _p, _r, _s) in refrs if b in models})
    soups = load_collision_soups(used, staging, quiet=quiet)
    walk_t, block_t = [], []
    for (base, pos, rot, scale) in refrs:
        w, b = soups.get(models.get(base), (None, None))
        if w is None and b is None:
            continue
        rmat = rot_matrix(*rot)
        p = np.asarray(pos, dtype=np.float64)
        for flat, sink in ((w, walk_t), (b, block_t)):
            placed = place(flat, rmat, scale, p)
            if placed is not None:
                sink.append(placed)
    if not quiet:
        print('%s: %d refrs, %d models, %d walkable, %d blocking tris'
              % (cell_name, len(refrs), len(soups),
                 sum(len(t) for t in walk_t), sum(len(t) for t in block_t)))
    return (np.concatenate(walk_t) if walk_t else np.zeros((0, 3, 3)),
            np.concatenate(block_t) if block_t else np.zeros((0, 3, 3)))


def default_esm(staging=STAGING):
    """Path to BSHeartland.esm inside the staging tree."""
    return os.path.join(staging, MESH_BSAS[0][0], 'BSHeartland.esm')


def main():
    """CLI: report the collision gathered for one Bruma cell."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cell')
    ap.add_argument('--esm')
    ap.add_argument('--staging', default=STAGING)
    a = ap.parse_args()
    w, b = cell_collision(a.esm or default_esm(a.staging), a.cell,
                          a.staging, quiet=False)
    if len(b):
        print('blocking z %.0f..%.0f' % (b[:, :, 2].min(), b[:, :, 2].max()))
    return 0


if __name__ == '__main__':
    sys.exit(main())
