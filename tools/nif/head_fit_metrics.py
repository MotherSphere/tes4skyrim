"""Head-gear / hair fit metrics: penetration of the head the game renders.

Grades a converted hair or helmet mesh against the Skyrim head it is worn on
and reports, per mesh:

  * tri-under    — hair TRIANGLES whose deepest interior point is inside the
    head.  This is the measurement that matters and the one a vertex-only
    check misses: a flat triangle spanning a domed skull dips between its
    corners, so a mesh whose every vertex clears the skin can still show
    scalp through the crown.  Sampled barycentrically (``--samples``, default
    8 -> 45 points per triangle).
  * worst        — the deepest such penetration, in Skyrim units.
  * standoff     — median/mean signed clearance over the on-head band, i.e.
    how far the mesh floats off the skin.  Vanilla Skyrim hair hugs; a large
    standoff reads in game as hair hovering.

MEASURE AGAINST THE REAL HEAD, NOT THE CAPPED ONE.  ``head_fit`` conforms
hair to an EAR-CAPPED skull (so ears never push hair outward) but penetration
must be judged against the surface the player actually sees.  Grading on the
capped head is what hid "hair under the skin" defects for several rounds:
one style measured 1 vertex under the capped head and 45 under the real one.
This tool always uses the real head (``sk_full_v`` / ``races_full``).

VIEW MODE (``--views``) grades what a camera SEES instead of what the
geometry does: the mesh and its head are z-buffered from a ring of
orthographic views, and per pixel it reports
  * clip         — hair covers the pixel but the SKIN is in front, with the
    hidden hair point inside the head: skin showing where the hair went
    under it.  Ear-shell pixels are counted apart (vanilla lets ears poke
    through hair).  Inner hair layers hidden behind outer hair never count.
  * clearance    — perpendicular clearance of the VISIBLE hair over the
    scalp band, per region (front/top/side/back): how close it reads.
``--source`` grades an Oblivion source hair on the Oblivion head (the
authored baseline); ``--morph`` puts a races.tri race morph (WoodElfRace...)
on the Skyrim head; ``--png DIR`` writes a contact sheet per mesh (hair
green = hugging -> red = standing off, magenta = clip, violet = ear clip).

Usage:
  python -m tools.nif.head_fit_metrics <mesh.nif> [<mesh.nif> ...]
  python -m tools.nif.head_fit_metrics --shipped                 # sweep output/
  python -m tools.nif.head_fit_metrics --shipped --race khajiit
  python -m tools.nif.head_fit_metrics --shipped --group elves --max 12
  python -m tools.nif.head_fit_metrics <mesh.nif> --female --dump 6
  python -m tools.nif.head_fit_metrics <mesh.nif> --views --png temp/hairviews
  python -m tools.nif.head_fit_metrics <source.nif> --views --source

A mesh's race/group is inferred from its filename suffix (``__ev`` elves,
``__or`` orc, ``__f`` female, a race token for beast packs) unless given
explicitly.
"""

import argparse
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scipy.spatial import cKDTree

from asset_convert.nif.sse_nif import read_nif
from pyffi.formats.nif import NifFormat
from asset_convert.character import head_fit
from asset_convert.character.facegen_tri import TriFile
from asset_convert.character.hair_plan import FAMILY_SUFFIX, FIT_ARGS
from asset_convert.sources.skyrim_assets import get_asset_bytes

NIF_MAGIC = (b'Gamebryo', b'NetImmer')
SHIPPED_DIR = os.path.join('output', 'Oblivion.esm', 'meshes', 'tes4',
                           'characters', 'hair')
#: head_fit race groups a mesh can be graded against.
GROUPS = ('elves', 'orc')
#: Points per closest-point solve; bounds peak memory.
CHUNK = 200000
#: Upper clearance of the on-head scalp band that standoff/closeness cover.
SCALP_BAND = 3.0
#: Orthographic pixel size, in head units.
PIXEL = 0.05
#: View ring elevations (degrees above the horizon).
VIEW_ELEVATIONS = (-10.0, 20.0, 50.0, 80.0)
#: View ring azimuth step (degrees); azimuth 0 looks at the face.
VIEW_AZIMUTH_STEP = 30.0
#: Views drawn into the --png contact sheet, as (elevation, azimuth).
SHEET_VIEWS = ((20.0, 0.0), (20.0, 60.0), (20.0, 90.0),
               (20.0, 150.0), (20.0, 180.0), (80.0, 0.0))
#: Hair this far behind the front skin is the far side of the head, not a clip.
CLIP_DEPTH = 2.0
#: Depth tolerance when deciding which surface is in front.
DEPTH_EPS = 1e-3
#: An ear vertex stands at least this far proud of the ear-capped skull.
EAR_PROUD = 0.02
#: Every Nth visible hair pixel gets a clearance reading (cost bound).
CLEAR_STRIDE = 3
#: Candidate pixels per rasterization chunk (memory bound).
RASTER_CHUNK = 3000000
REGIONS = ('front', 'top', 'side', 'back')


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def is_nif(path):
    """True when `path` starts with a NIF header."""
    try:
        with open(path, 'rb') as fh:
            return fh.read(8) in NIF_MAGIC
    except OSError:
        return False


def shape_tris(block):
    """(M,3) triangle indices of one geometry block; empty when unreadable."""
    try:
        tris = [tuple(x) for x in block.data.get_triangles()]
    except Exception:
        tris = []
    return np.array(tris, dtype=np.int64).reshape(-1, 3)


def load_shapes(path):
    """(verts, tris) of every geometry block, concatenated; any NIF format."""
    data = read_nif(str(path))
    vs, ts, off = [], [], 0
    for block in data.roots[0].tree():
        if not isinstance(block, (NifFormat.NiTriShape, NifFormat.NiTriStrips)):
            continue
        gd = block.data
        if gd is None or gd.num_vertices == 0:
            continue
        vs.append(np.array([[q.x, q.y, q.z] for q in gd.vertices],
                           dtype=np.float64))
        ts.append(shape_tris(block) + off)
        off += len(vs[-1])
    if not vs:
        return None, None
    return np.vstack(vs), np.vstack(ts)


def to_local(verts, origin):
    """Head-local coordinates; converted meshes are written in world space."""
    return verts - origin if np.abs(verts[:, 2]).max() > 60 else verts


# ---------------------------------------------------------------------------
# Heads
# ---------------------------------------------------------------------------

def real_head(female, race=None, group=None):
    """The head the GAME RENDERS, in head-local coordinates: (verts, tris)."""
    fit = head_fit._get(female)
    if fit is None:
        return None, None
    if race is not None:
        rf = fit.races_full.get(race)
        return (rf[0], rf[1]) if rf is not None else (None, None)
    if group:
        g = fit.groups.get(group)
        if g is not None:
            return g[2], fit.sk_t
    return fit.sk_full_v, fit.sk_t


def race_morph(female, morph, n):
    """(n,3) races.tri deltas of one race morph; rows past the tri stay zero."""
    rel = chr(92).join(['meshes', 'actors', 'character', 'character assets',
                        ('female' if female else 'male') + 'headraces.tri'])
    tri = TriFile.from_bytes(get_asset_bytes(rel))
    delta = np.zeros((n, 3))
    m = np.asarray(tri.morphs[morph], dtype=np.float64)
    delta[:len(m)] = m
    return delta


def capped_head(fit, race, group):
    """(real verts, ear-capped verts, tris) of a Skyrim head, or None."""
    if race is not None:
        if race not in fit.races_full:
            return None
        return fit.races_full[race][0], fit.races_sk[race][0], fit.races_sk[race][1]
    if group in fit.groups:
        _dv, cover, real = fit.groups[group]
        return real, cover, fit.sk_t
    return fit.sk_full_v, fit.sk_v, fit.sk_t


def head_surfaces(female, race=None, group=None, morph=None):
    """(verts, tris, ear-shell vert mask) of the Skyrim head, head-local.

    `morph` names a races.tri morph (WoodElfRace...) worn by the head.  The
    ear shell is where the real head stands proud of the ear-capped skull the
    fit conforms to.
    """
    got = capped_head(head_fit._get(female), race, group)
    if got is None:
        return None
    real, cover, tris = got
    if morph:
        delta = race_morph(female, morph, len(real))
        real, cover = real + delta, cover + delta
    out = real - real.mean(axis=0)
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    proud = np.einsum('vi,vi->v', real - cover, out) > EAR_PROUD
    return real, tris, proud


def oblivion_head(female, race=None):
    """(verts, tris, empty ear mask) of the Oblivion head hair was authored on."""
    fit = head_fit._get(female)
    pack = fit.races.get(race, fit.human)
    return pack.v, pack.t, np.zeros(len(pack.v), dtype=bool)


def infer(path):
    """(female, race, group) from a converted mesh's family suffix (hair_plan naming).

    A bare stem is its home family, which only the hair's EditorID knows
    (`ElfPonytail` -> style03.nif is elf-fitted): pass --group/--race for it.
    """
    low = os.path.basename(path).lower()
    family = next((f for f, suf in FAMILY_SUFFIX.items() if suf in low), None)
    if family is None:
        return '__f' in low, head_fit.fit_race_for_hair(low), None
    race, group = FIT_ARGS[family]
    return '__f' in low, race, group


def resolve(path, female, race, group):
    """(female, race, group): explicit values win over the filename's."""
    inf_f, inf_r, inf_g = infer(path)
    return (inf_f if female is None else female,
            inf_r if race is None else race,
            inf_g if group is None else group)


# ---------------------------------------------------------------------------
# Penetration metrics
# ---------------------------------------------------------------------------

def barycentric_grid(n):
    """(S,3) barycentric weights sampling a triangle's interior."""
    return np.array([(i / n, j / n, (n - i - j) / n)
                     for i in range(n + 1) for j in range(n + 1 - i)],
                    dtype=np.float64)


def clearance(P, head_v, head_t, tree):
    """Signed clearance of points P to the head, solved in bounded chunks."""
    parts = [head_fit._signed_clearance(P[i:i + CHUNK], head_v, head_t, tree)
             for i in range(0, len(P), CHUNK)]
    return np.concatenate(parts) if parts else np.zeros(0)


def triangle_min_clearance(local, tris, head_v, head_t, tree, samples):
    """Per-triangle deepest interior clearance against the head."""
    bw = barycentric_grid(samples)
    pts = (local[tris[:, 0]][:, None, :] * bw[None, :, 0, None]
           + local[tris[:, 1]][:, None, :] * bw[None, :, 1, None]
           + local[tris[:, 2]][:, None, :] * bw[None, :, 2, None])
    return clearance(pts.reshape(-1, 3), head_v, head_t,
                     tree).reshape(len(tris), -1).min(axis=1)


def dump_worst(local, tris, tmin, count):
    """Print the `count` deepest penetrating triangles with their centers."""
    under = tmin < 0
    centers = local[tris[under]].mean(axis=1)
    for k in np.argsort(tmin[under])[:count]:
        print('        depth %+.3f at x %+6.2f y %+6.2f z %+6.2f'
              % (tmin[under][k], centers[k, 0], centers[k, 1], centers[k, 2]))


def measure(path, female=None, race=None, group=None, samples=8, dump=0):
    """Print one line of penetration metrics; return the per-triangle min."""
    label = os.path.basename(path)
    female, race, group = resolve(path, female, race, group)
    verts, tris = load_shapes(path)
    if verts is None or not len(tris):
        print('  %-34s no geometry' % label)
        return None
    head_v, head_t = real_head(female, race, group)
    if head_v is None:
        print('  %-34s no fit data / head pack for race=%s' % (label, race))
        return None
    local = to_local(verts, head_fit._get(female).o_sk)
    tree = cKDTree(head_v[head_t].mean(axis=1))
    tmin = triangle_min_clearance(local, tris, head_v, head_t, tree, samples)
    clear = clearance(local, head_v, head_t, tree)
    band = clear < SCALP_BAND
    under = tmin < 0
    print('  %-34s tri-under %4d / %5d  worst %+.3f  standoff p50 %+.3f '
          'mean %+.3f'
          % (label, int(under.sum()), len(tris), float(tmin.min()),
             float(np.percentile(clear[band], 50)) if band.any() else float('nan'),
             float(clear[band].mean()) if band.any() else float('nan')))
    if dump and under.any():
        dump_worst(local, tris, tmin, dump)
    return tmin


def sweep(directory, race=None, group=None, limit=12, **kw):
    """Grade up to `limit` shipped meshes; plain human base variants by default."""
    n = 0
    for name in sorted(os.listdir(directory)):
        low = name.lower()
        path = os.path.join(directory, name)
        if not is_nif(path):
            continue
        if race and race not in low:
            continue
        if group and FAMILY_SUFFIX[group] not in low:
            continue
        if race is None and group is None and (
                '__' in low or head_fit.fit_race_for_hair(low)):
            continue
        measure(path, race=race, group=group, **kw)
        n += 1
        if n >= limit:
            break
    if not n:
        print('  (no matching meshes)')


# ---------------------------------------------------------------------------
# View metrics (z-buffered renders)
# ---------------------------------------------------------------------------

def view_basis(elev, azim):
    """(3,3) rows: screen right, screen up, toward the camera."""
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.sin(a), np.cos(e) * np.cos(a), np.sin(e)])
    up = (np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.99
          else np.array([0.0, -1.0, 0.0]))
    r = np.cross(up, d)
    r /= np.linalg.norm(r)
    return np.stack([r, np.cross(d, r), d])


def cross2(u, v):
    """z component of the 2-D cross product of row vectors."""
    return u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]


def raster_chunk(sel, px, z, T, box, W, depth, ids):
    """Rasterize triangles `sel` into flat depth/id buffers, front-most wins."""
    x0, y0, bw, n = box
    cnt = n[sel]
    tid = np.repeat(sel, cnt)
    k = np.arange(int(cnt.sum())) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    ix = x0[tid] + k % bw[tid]
    iy = y0[tid] + k // bw[tid]
    p = np.stack([ix + 0.5, iy + 0.5], axis=1)
    a, b, c = px[T[tid, 0]], px[T[tid, 1]], px[T[tid, 2]]
    area = cross2(b - a, c - a)
    safe = np.where(np.abs(area) > 1e-12, area, np.inf)
    wa = cross2(b - p, c - p) / safe
    wb = cross2(c - p, a - p) / safe
    wc = 1.0 - wa - wb
    zz = wa * z[T[tid, 0]] + wb * z[T[tid, 1]] + wc * z[T[tid, 2]]
    pix = iy * W + ix
    keep = (np.isfinite(safe) & (wa >= 0) & (wb >= 0) & (wc >= 0)
            & (zz > depth[pix]))
    pix, zz, tid = pix[keep], zz[keep], tid[keep]
    order = np.lexsort((-zz, pix))
    pix, zz, tid = pix[order], zz[order], tid[order]
    first = np.r_[True, pix[1:] != pix[:-1]] if len(pix) else np.zeros(0, bool)
    depth[pix[first]] = zz[first]
    ids[pix[first]] = tid[first]


def rasterize(S, T, lo, shape):
    """Front-most (depth, triangle id) per pixel of screen-space verts S.

    S rows are (right, up, toward-camera); empty pixels hold -inf / -1.
    """
    H, W = shape
    px = (S[:, :2] - lo) / PIXEL
    tri = px[T]
    x0 = np.clip(np.floor(tri[:, :, 0].min(axis=1)).astype(np.int64), 0, W - 1)
    x1 = np.clip(np.floor(tri[:, :, 0].max(axis=1)).astype(np.int64), 0, W - 1)
    y0 = np.clip(np.floor(tri[:, :, 1].min(axis=1)).astype(np.int64), 0, H - 1)
    y1 = np.clip(np.floor(tri[:, :, 1].max(axis=1)).astype(np.int64), 0, H - 1)
    bw = x1 - x0 + 1
    n = bw * (y1 - y0 + 1)
    depth = np.full(H * W, -np.inf)
    ids = np.full(H * W, -1, dtype=np.int64)
    ends = np.cumsum(n)
    start = 0
    while start < len(T):
        stop = int(np.searchsorted(ends, ends[start] - n[start] + RASTER_CHUNK,
                                   side='right'))
        stop = max(stop, start + 1)
        raster_chunk(np.arange(start, stop), px, S[:, 2], T, (x0, y0, bw, n),
                     W, depth, ids)
        start = stop
    return depth.reshape(H, W), ids.reshape(H, W)


def regions_of(P, center):
    """Region index per point (see REGIONS) by direction from the head center."""
    d = P - center
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    reg = np.full(len(P), 2, dtype=np.int8)
    reg[d[:, 1] > 0.45] = 0
    reg[d[:, 1] < -0.45] = 3
    reg[d[:, 2] > 0.7] = 1
    return reg


def unproject(basis, lo, rows, cols, depth):
    """Head-local 3-D points of the given pixels at the given depths."""
    s = np.stack([lo[0] + (cols + 0.5) * PIXEL, lo[1] + (rows + 0.5) * PIXEL,
                  depth], axis=1)
    return s @ basis


def classify_view(basis, scene, full):
    """One view's per-pixel result as a dict of (H,W) images.

    cls: 0 empty, 1 skin, 2 visible hair, 3 clip (hair gone under the
    skin), 4 ear clip.  clear: hair clearance, filled for clipped pixels and
    for every visible-hair pixel when `full`, else every CLEAR_STRIDE-th.
    reg: region index where clear is filled.
    """
    (hv, ht), (sv, st, ear_tri), tree, center = scene
    Sh, Ss = hv @ basis.T, sv @ basis.T
    both = np.vstack([Sh[:, :2], Ss[:, :2]])
    lo = both.min(axis=0) - 2 * PIXEL
    shape = tuple((np.ceil((both.max(axis=0) - lo) / PIXEL).astype(int) + 2)[::-1])
    zh, _ih = rasterize(Sh, ht, lo, shape)
    zs, i_s = rasterize(Ss, st, lo, shape)
    has_h = np.isfinite(zh)
    gap = np.full(shape, -np.inf)
    both_hit = has_h & np.isfinite(zs)
    gap[both_hit] = zs[both_hit] - zh[both_hit]
    near = (gap > DEPTH_EPS) & (gap < CLIP_DEPTH)
    visible = has_h & ~(zs > zh + DEPTH_EPS)
    cls = np.where(np.isfinite(zs), 1, 0).astype(np.int8)
    cls[visible] = 2
    clear = np.full(shape, np.nan)
    reg = np.full(shape, -1, dtype=np.int8)
    vr, vc = np.nonzero(visible)
    if not full:
        vr, vc = vr[::CLEAR_STRIDE], vc[::CLEAR_STRIDE]
    nr, nc = np.nonzero(near)
    rows, cols = np.r_[vr, nr], np.r_[vc, nc]
    P = unproject(basis, lo, rows, cols, zh[rows, cols])
    clear[rows, cols] = clearance(P, sv, st, tree)
    reg[rows, cols] = regions_of(P, center)
    under = near & (np.nan_to_num(clear, nan=1.0) < 0)
    cls[under] = np.where(ear_tri[i_s[under]], 4, 3)
    shade = np.abs(head_fit._tri_normals(sv, st) @ basis[2])[i_s]
    return {'cls': cls, 'clear': clear, 'reg': reg, 'has_h': has_h,
            'shade': np.where(i_s >= 0, shade, 0.0)}


def build_scene(path, female, race, group, morph, source):
    """((hair v, t), (head v, t, ear-tri mask), tree, center), or None."""
    verts, tris = load_shapes(path)
    fit = head_fit._get(female)
    if verts is None or fit is None or not len(tris):
        return None
    if source:
        head = oblivion_head(female, race)
    else:
        head = head_surfaces(female, race, group, morph)
        verts = to_local(verts, fit.o_sk)
    if head is None:
        return None
    hv, ht, ear = head
    lo, hi = hv.min(axis=0), hv.max(axis=0)
    center = np.array([0.0, (lo[1] + hi[1]) / 2,
                       hi[2] - 0.45 * (hi[0] - lo[0])])
    return ((verts, tris), (hv, ht, ear[ht].any(axis=1)),
            cKDTree(hv[ht].mean(axis=1)), center)


def accumulate(tally, view):
    """Add one classified view's counts and clearance samples to `tally`."""
    cls, clear, reg = view['cls'], view['clear'], view['reg']
    tally['hair'] += int(view['has_h'].sum())
    for i in range(len(REGIONS)):
        in_r = reg == i
        tally['clip'][i] += int((in_r & (cls == 3)).sum())
        tally['ear'][i] += int((in_r & (cls == 4)).sum())
        vis = in_r & (cls == 2) & (clear < SCALP_BAND)
        tally['vis'][i].append(clear[vis])


def report(label, tally):
    """Print the view-mode summary lines for one mesh."""
    hair = max(tally['hair'], 1)
    clip, ear = sum(tally['clip']), sum(tally['ear'])
    print('  %-34s clip %.3f%%  ear-clip %.3f%%  of %d hair px'
          % (label, 100.0 * clip / hair, 100.0 * ear / hair, tally['hair']))
    for i, name in enumerate(REGIONS):
        c = np.concatenate(tally['vis'][i]) if tally['vis'][i] else np.zeros(0)
        if not len(c):
            print('        %-5s (no visible scalp hair)' % name)
            continue
        print('        %-5s clip %6d px  visible p10 %+.3f  p50 %+.3f  p90 %+.3f'
              '  >0.25: %4.1f%%  >0.50: %4.1f%%'
              % (name, tally['clip'][i], *np.percentile(c, [10, 50, 90]),
                 100.0 * (c > 0.25).mean(), 100.0 * (c > 0.5).mean()))


def measure_views(path, female=None, race=None, group=None, morph=None,
                  source=False, png=None):
    """Render the mesh on its head over the view ring; print clip + closeness."""
    label = os.path.basename(path)
    female, race, group = resolve(path, female, race, group)
    scene = build_scene(path, female, race, group, morph, source)
    if scene is None:
        print('  %-34s no geometry / head for race=%s' % (label, race))
        return None
    tally = {'hair': 0, 'clip': [0] * len(REGIONS), 'ear': [0] * len(REGIONS),
             'vis': [[] for _ in REGIONS]}
    for elev in VIEW_ELEVATIONS:
        for azim in np.arange(0.0, 360.0, VIEW_AZIMUTH_STEP):
            accumulate(tally, classify_view(view_basis(elev, azim), scene, False))
    report(label + (' [%s]' % morph if morph else ''), tally)
    if png:
        write_sheet(scene, os.path.join(png, Path(path).stem
                                        + ('_' + morph if morph else '')
                                        + ('_src' if source else '') + '.png'))
    return tally


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

def panel_rgb(view):
    """(H,W,3) uint8 image of one classified view, flipped to screen rows."""
    cls, clear = view['cls'], view['clear']
    img = np.zeros(cls.shape + (3,), dtype=np.uint8)
    img[:] = (22, 24, 28)
    grey = (60 + 170 * view['shade']).astype(np.uint8)
    img[cls == 1] = np.stack([grey] * 3, axis=-1)[cls == 1]
    t = np.clip(np.nan_to_num(clear, nan=0.0) / 0.5, 0.0, 1.0)
    hair = np.stack([80 + 175 * t, 210 - 150 * t, 70 + 0 * t], axis=-1)
    tails = np.isfinite(clear) & (clear >= SCALP_BAND)
    hair[tails] = (150, 130, 100)
    img[cls == 2] = hair[cls == 2].astype(np.uint8)
    img[cls == 3] = (255, 0, 255)
    img[cls == 4] = (120, 60, 170)
    return img[::-1]


def write_sheet(scene, out_path):
    """Save a labelled grid of SHEET_VIEWS renders to `out_path`."""
    from PIL import Image, ImageDraw
    panels = []
    for elev, azim in SHEET_VIEWS:
        im = Image.fromarray(panel_rgb(classify_view(view_basis(elev, azim),
                                                     scene, True)))
        ImageDraw.Draw(im).text((6, 4), 'elev %d azim %d' % (elev, azim),
                                fill=(240, 240, 200))
        panels.append(im)
    w = max(p.width for p in panels)
    h = max(p.height for p in panels)
    sheet = Image.new('RGB', (3 * w, 2 * h), (22, 24, 28))
    for i, p in enumerate(panels):
        sheet.paste(p, ((i % 3) * w, (i // 3) * h))
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    sheet.save(out_path)
    print('        sheet -> %s' % out_path)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def parse_args():
    """The command line options."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('meshes', nargs='*', help='converted .nif files to grade')
    ap.add_argument('--shipped', action='store_true',
                    help='sweep the converted hair in output/')
    ap.add_argument('--dir', default=SHIPPED_DIR,
                    help='directory for --shipped (default: %(default)s)')
    ap.add_argument('--race', choices=sorted(head_fit._RACE_PACKS),
                    help='beast race pack (default: infer from filename)')
    ap.add_argument('--group', choices=GROUPS,
                    help='race group (default: infer from filename)')
    ap.add_argument('--female', action='store_true',
                    help='grade against the female head')
    ap.add_argument('--samples', type=int, default=8,
                    help='barycentric subdivision per triangle '
                         '(default: %(default)s -> 45 points)')
    ap.add_argument('--dump', type=int, default=0,
                    help='print the N deepest penetrations with positions')
    ap.add_argument('--max', type=int, default=12,
                    help='max meshes for --shipped (default: %(default)s)')
    ap.add_argument('--views', action='store_true',
                    help='grade what a camera sees (z-buffered view ring)')
    ap.add_argument('--source', action='store_true',
                    help='--views: an Oblivion source mesh on the Oblivion head')
    ap.add_argument('--morph', help='--views: races.tri morph(s) worn by the '
                                    'Skyrim head, comma-separated, e.g. '
                                    'WoodElfRace,DarkElfRace')
    ap.add_argument('--png', help='--views: write a contact sheet per mesh here')
    return ap, ap.parse_args()


def main():
    """Command line entry point."""
    ap, args = parse_args()
    female = args.female or None
    if args.views:
        for path in args.meshes:
            for morph in (args.morph or '').split(',') if args.morph else [None]:
                measure_views(path, female=female, race=args.race,
                              group=args.group, morph=morph,
                              source=args.source, png=args.png)
    elif args.shipped:
        sweep(args.dir, race=args.race, group=args.group, limit=args.max,
              samples=args.samples, dump=args.dump)
    elif args.meshes:
        for path in args.meshes:
            measure(path, female=female, race=args.race, group=args.group,
                    samples=args.samples, dump=args.dump)
    else:
        ap.error('give mesh paths or --shipped')


if __name__ == '__main__':
    main()
