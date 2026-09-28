"""Hand-pinned navmesh floor: triangles the generator must never cut away.

A correction in `tests/navmesh_fixed/` is a snapshot keyed by triangle INDEX,
so it decays the moment the generator moves and it is gitignored.  A pin is the
durable half of the same intent: the WORLD POSITIONS a human declared walkable,
which survive any retriangulation and are small enough to commit and review.

    from tes5_import.base.navmesh_pins import pins_for
    pts = pins_for('Oblivion.esm', 'ImperialDungeon02')

Pins ride `corridor_clean.finalize`'s existing `pin_xy` mechanism.  They protect
existing floor; they do not make the generator REACH ground it never grew.

This module lives OUTSIDE `tes5_import/navmesh/` on purpose: that folder's
bytes are the navmesh cache tag.

See: docs/commentary/tes5_import_navmesh.md#pinned-navmesh-floor
"""

import json
import os

from tes5_import.base.navmesh_frozen import (
    FROZEN_VERSION, SNAP_TOL, STOREY_BAND, apply_frozen, drop_unused_verts,
    plane_z,
)

#: Committable pin files, one per source plugin.
PINS = 'navmesh_pins'

#: Every section of a pin file, each `{cell key: [row, ...]}`.
PARTS = ('cells', 'welds', 'cuts', 'frozen', 'voids')

#: Floats per row of the sections whose rows have a fixed width.
ROW_WIDTH = {'cells': 3, 'welds': 6, 'frozen': 9, 'voids': 9}

#: Parsed pin files, keyed by plugin; a missing file caches as {}.
_CACHE = {}

#: How near a generated vertex must be to a weld endpoint to BE that endpoint.
WELD_TOLERANCE = 8.0


def pins_path(plugin):
    """Path of the pin file for one source plugin."""
    return os.path.join(PINS, '%s.json' % plugin)


def _read(plugin):
    """The parsed pin document on disk, or an empty one.

    A malformed or absent file answers empty: a pin is an optimisation of
    human intent, never a thing whose absence may abort a conversion.
    """
    out = {part: {} for part in PARTS}
    try:
        with open(pins_path(plugin), encoding='utf-8') as fh:
            got = json.load(fh)
    except (OSError, ValueError):
        return out
    if not isinstance(got, dict):
        return out
    for part in PARTS:
        section = got.get(part)
        if isinstance(section, dict):
            out[part] = {k: v for k, v in section.items()
                         if isinstance(v, list)}
    return out


def load(plugin):
    """One plugin's whole pin document, read at most once."""
    if plugin not in _CACHE:
        _CACHE[plugin] = _read(plugin)
    return _CACHE[plugin]


def _section(plugin, part, key):
    """One cell's raw entry from `part`, matched case-insensitively."""
    if not plugin or not key:
        return []
    cells = load(plugin).get(part, {})
    got = cells.get(key)
    if got is None:
        want = key.lower()
        for name, val in cells.items():
            if name.lower() == want:
                return val
    return got or []


def plugin_of(geom_cache_dir):
    """Plugin owning a `<export>/<plugin>/navmesh_geom_cache` dir, any spelling.

    See: docs/commentary/tes5_import_navmesh.md#mixed-separators-lost-the-pins
    """
    flat = str(geom_cache_dir or '').replace('\\', '/').rstrip('/')
    return flat.rsplit('/', 2)[-2] if '/' in flat else ''


def cell_key(cell_rec, wrld_fid=0, grid=None):
    """The key a cell is stored under: its EditorID, else "wrld:FID X Y".

    An exterior CELL has no EditorID.  The generator knows its worldspace only
    as a FormID, so that is what names it -- threading the WRLD EditorID into
    every navmesh worker would be real plumbing for a file nobody reads by eye.

    See: docs/commentary/tes5_import_navmesh.md#pinned-navmesh-floor
    """
    edid = (cell_rec or {}).get('EditorID') or ''
    if edid:
        return edid
    if grid is None or not wrld_fid:
        return ''
    return 'wrld:%06X %d %d' % (wrld_fid & 0x00FFFFFF, grid[0], grid[1])


def pins_for(plugin, key):
    """`[(x, y, z), ...]` of floor pinned walkable in one cell, or `[]`."""
    return [tuple(float(c) for c in p[:3])
            for p in _section(plugin, 'cells', key) if len(p) >= 3]


def welds_for(plugin, key):
    """`[((x,y,z) from, (x,y,z) to), ...]` cracks to close in one cell.

    A crack closes only when two triangles SHARE a vertex index, so a weld
    names the two PLACES whose vertices must become one -- a position pair
    survives regeneration where the editor's index pair cannot.

    See: docs/commentary/tes5_import_navmesh.md#pinned-navmesh-floor
    """
    out = []
    for w in _section(plugin, 'welds', key):
        if len(w) >= 6:
            out.append((tuple(float(c) for c in w[:3]),
                        tuple(float(c) for c in w[3:6])))
    return out


def cuts_for(plugin, key):
    """`[(zmin, zmax, [(x, y), ...]), ...]` regions to strip from one cell's navmesh.

    A row is `[zmin, zmax, x1, y1, x2, y2, x3, y3, ...]`: a polygon of at
    least three corners in world XY plus the height band it applies to.
    See: docs/commentary/tes5_import_navmesh.md#cut-pins
    """
    out = []
    for row in _section(plugin, 'cuts', key):
        if len(row) >= 8 and len(row) % 2 == 0:
            vals = [float(c) for c in row]
            out.append((vals[0], vals[1], list(zip(vals[2::2], vals[3::2]))))
    return out


def tris_for(plugin, part, key):
    """`[((x,y,z), (x,y,z), (x,y,z)), ...]` of one cell's `frozen` or `voids` rows.

    See: docs/commentary/tes5_import_navmesh.md#frozen-navmesh-patches
    """
    return [tuple(tuple(float(c) for c in r[k:k + 3]) for k in (0, 3, 6))
            for r in _section(plugin, part, key) if len(r) >= 9]


def hand_edits_for(plugin, key):
    """Every correction a human committed for one cell, by section name."""
    return {'pins': pins_for(plugin, key), 'welds': welds_for(plugin, key),
            'cuts': cuts_for(plugin, key),
            'frozen': tris_for(plugin, 'frozen', key),
            'voids': tris_for(plugin, 'voids', key)}


def apply_hand_edits(verts, tris, ledges, edits):
    """(verts, tris, ledges) after the post-build corrections: cuts, then frozen patches.

    See: docs/commentary/tes5_import_navmesh.md#frozen-navmesh-patches
    """
    edits = edits or {}
    verts, tris, ledges = apply_cuts(verts, tris, ledges, edits.get('cuts'))
    return apply_frozen(verts, tris, ledges, edits.get('frozen') or [],
                        edits.get('voids') or [])


def _inside(x, y, poly):
    """True when (x, y) lies inside the polygon (even-odd rule)."""
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _is_cut(verts, tri, cuts):
    """True when the triangle's centroid falls inside any cut region and band."""
    cx, cy, cz = (sum(verts[i][k] for i in tri[:3]) / 3.0 for k in range(3))
    return any(zmin <= cz <= zmax and _inside(cx, cy, poly)
               for zmin, zmax, poly in cuts)


def apply_cuts(verts, tris, ledges, cuts):
    """(verts, tris, ledges) with every cut triangle removed and indices compacted.

    Ledge links naming a removed triangle are dropped with it.
    See: docs/commentary/tes5_import_navmesh.md#cut-pins
    """
    if not cuts or not tris:
        return verts, tris, ledges
    keep = [i for i, t in enumerate(tris) if not _is_cut(verts, t, cuts)]
    if len(keep) == len(tris):
        return verts, tris, ledges
    tri_map = {old: new for new, old in enumerate(keep)}
    new_ledges = [(tri_map[u], tri_map[l]) + tuple(rest)
                  for (u, l, *rest) in ledges or ()
                  if u in tri_map and l in tri_map]
    new_verts, new_tris = drop_unused_verts(verts, [tris[i] for i in keep])
    return new_verts, new_tris, new_ledges


def digest(plugin, key):
    """A stable string for `geom_hash`, so pinning one cell restages only it.

    Empty when the cell has no pins, welds or cuts, which keeps every
    unpinned cell's hash exactly what it was before pins existed.
    """
    parts = ['%.2f,%.2f,%.2f' % p for p in pins_for(plugin, key)]
    parts += ['W%.2f,%.2f,%.2f>%.2f,%.2f,%.2f' % (a + b)
              for (a, b) in welds_for(plugin, key)]
    parts += ['C%.2f,%.2f:' % (zmin, zmax)
              + ';'.join('%.2f,%.2f' % p for p in poly)
              for (zmin, zmax, poly) in cuts_for(plugin, key)]
    for part in ('frozen', 'voids'):
        parts += [part[0].upper() + ';'.join('%.2f,%.2f,%.2f' % p for p in t)
                  for t in tris_for(plugin, part, key)]
    if any(tris_for(plugin, part, key) for part in ('frozen', 'voids')):
        parts.append('V%d' % FROZEN_VERSION)
    return '|'.join(parts)


def _rounded(rows, width):
    """`rows` as plain lists of `width` floats at 0.01u, dropping short ones."""
    return [[round(float(c), 2) for c in r[:width]]
            for r in rows or () if len(r) >= width]


def _flat(points):
    """A sequence of (x, y, z) points as one flat row."""
    return [float(c) for p in points for c in p[:3]]


def _write(plugin, doc):
    """Write one plugin's whole pin document and drop its cached read."""
    if not os.path.isdir(PINS):
        os.makedirs(PINS)
    path = pins_path(plugin)
    body = {'plugin': plugin}
    body.update({part: doc[part] for part in PARTS})
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(body, fh, indent=1, sort_keys=True)
        fh.write('\n')
    _CACHE.pop(plugin, None)
    return path


def save(plugin, key, points=None, welds=None, frozen=None, voids=None):
    """Replace the given sections of one cell, creating the file on first use.

    A section passed as None is left alone; an empty one clears the cell from
    it.  `welds` are `(from, to)` pairs, `frozen`/`voids` triangles of three
    points.  Values round to 0.01u so float noise never churns the diff.
    Returns `(path, {section: rows now stored})`.
    """
    doc = _read(plugin)
    given = {'cells': points,
             'welds': None if welds is None else [_flat(w) for w in welds],
             'frozen': None if frozen is None else [_flat(t) for t in frozen],
             'voids': None if voids is None else [_flat(t) for t in voids]}
    for part, rows in given.items():
        if rows is None:
            continue
        got = _rounded(rows, ROW_WIDTH[part])
        if got:
            doc[part][key] = got
        else:
            doc[part].pop(key, None)
    path = _write(plugin, doc)
    return path, {part: len(doc[part].get(key, ())) for part in PARTS}


def _touches(a, b):
    """True when two patch triangles share a corner (to 0.5u in plan, same storey)."""
    return any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 <= SNAP_TOL ** 2
               and abs(p[2] - q[2]) <= STOREY_BAND for p in a for q in b)


def _holds(tri, point):
    """True when `point` is inside `tri` in plan at its storey, or on one of its corners."""
    x, y, z = point[:3]
    if any((p[0] - x) ** 2 + (p[1] - y) ** 2 <= 4.0 and abs(p[2] - z) <= STOREY_BAND
           for p in tri):
        return True
    return (_inside(x, y, [p[:2] for p in tri])
            and abs(plane_z(tri, x, y) - z) <= STOREY_BAND)


def _corner_buckets(rows):
    """`{1u plan bucket: {row index}}` over every corner of every row."""
    out = {}
    for i, t in enumerate(rows):
        for p in t:
            out.setdefault((int(p[0] // 1.0), int(p[1] // 1.0)), set()).add(i)
    return out


def _rows_near(buckets, p):
    """Row indices with a corner in the 3x3 buckets around point `p`."""
    bx, by = int(p[0] // 1.0), int(p[1] // 1.0)
    return {j for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            for j in buckets.get((bx + dx, by + dy), ())}


def patch_at(rows, point):
    """Indices of `rows` in the patch holding `point`: every triangle joined to it by corners."""
    buckets = _corner_buckets(rows)
    todo = [i for i, t in enumerate(rows) if _holds(t, point)]
    seen = set(todo)
    while todo:
        i = todo.pop()
        near = set().union(*(_rows_near(buckets, p) for p in rows[i]))
        for j in near - seen:
            if _touches(rows[i], rows[j]):
                seen.add(j)
                todo.append(j)
    return seen


def remove_patch(plugin, key, point=None):
    """Unpin the frozen patch holding `point`, or every patch in the cell when None.

    Returns `(path, frozen rows removed, void rows removed)`.
    See: docs/commentary/tes5_import_navmesh.md#frozen-navmesh-patches
    """
    frozen = tris_for(plugin, 'frozen', key)
    voids = tris_for(plugin, 'voids', key)
    nf = len(frozen)
    gone = (set(range(nf + len(voids))) if point is None
            else patch_at(frozen + voids, point))
    keep_f = [t for i, t in enumerate(frozen) if i not in gone]
    keep_v = [t for i, t in enumerate(voids) if i + nf not in gone]
    path, _n = save(plugin, key, frozen=keep_f, voids=keep_v)
    return path, nf - len(keep_f), len(voids) - len(keep_v)
