"""Web editor for hand-placing transplanted pathgrid nodes.

Dragging a node beats reading its coordinate off a grid and issuing a `move`
command, and the corpus is already a small JSON the page can read and write.

The page draws Bruma's REAL collision (walls, pillars, benches -- the same
Havok soup the Oblivion-side renders use), the authored navmesh as a dim
underlay, then the pathgrid on top.  Nodes are placed against the WALLS; the
authored mesh is context only, because a grid fitted to the answer would leak
the answer into the input.

    python tools/navmesh/transplant_server.py            # all corpus cells
    python tools/navmesh/transplant_server.py --port 8765

Geometry is baked to JSON once per cell and cached in memory: gathering a
cell's collision takes seconds, and the page re-fetches on every cell switch.

See: docs/commentary/tes5_import_navmesh.md#transplant-editor
"""

import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import unquote_plus

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def query_params(query):
    """A query string as a dict, values URL-decoded."""
    out = {}
    for part in query.split('&'):
        k, _, v = part.partition('=')
        if k:
            out[k] = unquote_plus(v)
    return out

from tes5_import.navmesh import corridor
from tools.navmesh.authored import load_authored, load_authored_full
from tools.navmesh.bruma_collision import cell_collision, default_esm
from tools.navmesh.draw import tri_class
from tools.navmesh.meshedit import (
    is_stale, load_fix, make_entry, save_fix,
)


def plugins():
    """Exports that have a built audit index."""
    root = 'export'
    if not os.path.isdir(root):
        return []
    return sorted(d for d in os.listdir(root)
                  if os.path.isfile(os.path.join(root, d, 'audit_index3.pkl')))


def plugin_cells(plugin, prefix=''):
    """EditorIDs in `plugin` that have a pathgrid, optionally filtered."""
    idx = index_for(os.path.join('export', plugin))
    want = prefix.lower()
    out = []
    for rec in idx.cells:
        eid = rec.get('EditorID') or ''
        if eid and want in eid.lower() and idx.pgrd_by_cell.get(rec['FormID']):
            out.append(eid)
    return sorted(out)


def mesh_bake(plugin, cell):
    """Our mesh, its collision and any saved correction, in the CELL's frame.

    No fit is applied: an arbitrary cell has no Bruma counterpart to align to,
    and editing triangles against their own collision is the point.

    See: docs/commentary/tes5_import_navmesh.md#hand-corrected-navmesh-corpus
    """
    ck = ('mesh', plugin, cell)
    if ck in _CACHE:
        return _CACHE[ck]
    idx = index_for(os.path.join('export', plugin))
    src = idx.cell(cell)
    if src is None:
        return {'error': 'no cell %r in %s' % (cell, plugin)}
    ledges = []
    verts, tris = (src.build(ledges_out=ledges) if src.has_pathgrid
                   else ([], []))
    walk, block = src.collision()
    fix = load_fix(plugin, cell)
    out = {
        'plugin': plugin,
        'cell': cell,
        'verts': [[round(float(c), 2) for c in p] for p in verts],
        'tris': [[int(i) for i in t] for t in tris],
        'tri_class': [tri_class(verts, t) for t in tris],
        'doors': our_doors(src, verts, tris),
        'ledges': [[int(a), int(b), round(float(d), 1)]
                   for (a, b, d) in ledges],
        'walkable': _flatten(walk),
        'blocking': _flatten(block),
        'nodes': [[round(float(c), 1) for c in p] for p in src.nodes],
        'edges': [list(e) for e in src.edges],
        'ops': (fix or {}).get('ops', []),
        'stale': is_stale(fix, verts, tris) if fix else False,
    }
    _CACHE[ck] = out
    return out


def mesh_save(plugin, cell, payload):
    """Commit a correction's ops, re-baking `result` from the live mesh."""
    idx = index_for(os.path.join('export', plugin))
    src = idx.cell(cell)
    if src is None:
        return {'error': 'no cell %r in %s' % (cell, plugin)}
    ledges = []
    verts, tris = (src.build(ledges_out=ledges) if src.has_pathgrid
                   else ([], []))
    ops = payload.get('ops') or []
    entry = make_entry(plugin, cell, verts, tris, ops,
                       our_doors(src, verts, tris),
                       [(int(a), int(b)) for (a, b, _d) in ledges])
    path = save_fix(plugin, cell, entry)
    _CACHE.pop(('mesh', plugin, cell), None)
    return {'saved': path, 'ops': len(ops),
            'tris': len(entry['result']['tris'])}


def our_doors(cell, verts, tris):
    """Indices of OUR triangles a door threshold stands on.

    Uses production's own `_tri_carries_door`, so what the page marks is what
    the writer would flag -- a second predicate here could disagree silently.
    """
    xy = [(x, y, z) for (x, y, z, _r, _f, _tp, _w) in cell.doors]
    if not xy:
        return []
    return [i for i, t in enumerate(tris)
            if corridor._tri_carries_door(verts, t, xy)]
from tools.navmesh.transplant import (
    CORPUS, DEFAULT_EXPORT, apply_fit, index_for, load, occupancy,
    placed_nodes, save,
)

_PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'transplant_editor.html')


def _generated(entry):
    """`(flat tris, shape verdicts, door tri indices)` for OUR fitted mesh.

    The verdict is `draw.tri_class`, so the page colours our mesh exactly as
    `render.py` does; the editor and the preview must not disagree.

    See: docs/commentary/tes5_import_navmesh.md#renderer-colour-contract
    """
    idx = index_for(entry.get('export', DEFAULT_EXPORT))
    src = idx.cell(entry['source_cell'])
    if src is None or not src.has_pathgrid:
        return [], [], []
    verts, tris = src.build()
    cls = [tri_class(verts, t) for t in tris]
    doors = our_doors(src, verts, tris)
    fit = apply_fit([tuple(p) for p in verts], entry['fit'])
    flat = _flatten([(fit[a], fit[b], fit[c]) for (a, b, c) in tris])
    return flat, cls, doors


def _authored_full(entry):
    """`(flat tris, door-flagged tri indices)` for the authored answer key."""
    averts, atris, adoors = load_authored_full(entry['authored_esm'],
                                               entry['authored_cell'])
    return [(averts[a], averts[b], averts[c]) for (a, b, c) in atris], adoors

#: Baked geometry per cell, so switching back is instant.
_CACHE = {}


def cells():
    """Every cell EditorID in the corpus."""
    if not os.path.isdir(CORPUS):
        return []
    return sorted(f[:-5] for f in os.listdir(CORPUS) if f.endswith('.json'))


def _flatten(tris):
    """Triangles as a flat [x0,y0,z0,x1,y1,z1,...] list.

    Z ships too: the elevation view draws the same triangles projected onto
    X/Z or Y/Z, so dropping it would mean a second round trip per cell.
    """
    out = []
    for t in tris:
        for p in (t[0], t[1], t[2]):
            out += [round(float(p[0]), 1), round(float(p[1]), 1),
                    round(float(p[2]), 1)]
    return out


def _clip_z(tris, zlo, zhi):
    """Collision triangles overlapping the [zlo, zhi] slab."""
    return [t for t in tris
            if min(p[2] for p in t) <= zhi and max(p[2] for p in t) >= zlo]


def _fit_tris(tris, fit):
    """Apply a corpus fit (rotation + offset) to whole triangles."""
    return [tuple(apply_fit([tuple(p) for p in t], fit)) for t in tris]


def _oblivion_collision(entry, zlo, zhi):
    """The SOURCE cell's collision, mapped through the fit into Bruma's frame.

    Showing both sides in one frame makes "which statics moved" a question you
    answer by toggling, rather than from memory.
    """
    idx = index_for(entry.get('export', DEFAULT_EXPORT))
    src = idx.cell(entry['source_cell'])
    if src is None:
        return [], []
    walk, block = src.collision()
    return (_clip_z(_fit_tris(walk, entry['fit']), zlo, zhi),
            _clip_z(_fit_tris(block, entry['fit']), zlo, zhi))


def bake(cell):
    """All geometry the page needs for `cell`, as a JSON-ready dict."""
    if cell in _CACHE:
        return _CACHE[cell]
    entry = load(cell)
    nodes, edges = placed_nodes(cell, entry=entry)
    tris, adoors = _authored_full(entry)
    zs = [p[2] for t in tris for p in t] or [0.0]
    lo, hi = min(zs) - 64.0, max(zs) + 160.0
    walk, block = cell_collision(default_esm(), entry['authored_cell'])
    owalk, oblock = _oblivion_collision(entry, lo, hi)
    gen, gen_class, gen_doors = _generated(entry)
    out = {
        'cell': cell,
        'source_cell': entry['source_cell'],
        'authored_cell': entry['authored_cell'],
        'authored': _flatten(tris),
        'authored_doors': adoors,
        'generated': gen,
        'generated_class': gen_class,
        'generated_doors': gen_doors,
        'walkable': _flatten(_clip_z(walk, lo, hi)),
        'blocking': _flatten(_clip_z(block, lo, hi)),
        'ob_walkable': _flatten(owalk),
        'ob_blocking': _flatten(oblock),
        'nodes': [[round(p[0], 1), round(p[1], 1), round(p[2], 1)]
                  for p in nodes],
        'edges': [list(e) for e in edges],
        'moved': sorted(int(k) for k in entry.get('moved', {})),
        'dropped': sorted(entry.get('dropped', [])),
    }
    _CACHE[cell] = out
    return out


def _n_source(entry):
    """How many nodes come from the source grid, before any `added` ones."""
    nodes, _e = placed_nodes(entry['cell'], entry=entry)
    return len(nodes) - len(entry.get('added', []))


def apply_edits(cell, payload):
    """Write every edit kind into the corpus; returns a summary.

    A moved node that is one of the `added` ones is rewritten in place rather
    than pushed into `moved`, which is keyed against the source grid.
    """
    entry = load(cell)
    if entry is None:
        return {'ok': False, 'error': 'no corpus entry for %s' % cell}
    nodes, _e = placed_nodes(cell, entry=entry)
    base = _n_source(entry)
    added = [list(p) for p in entry.get('added', [])]
    added += [[float(p[0]), float(p[1]), float(p[2])]
              for p in (payload.get('added') or [])]
    moved = entry.setdefault('moved', {})
    for k, xyz in (payload.get('moved') or {}).items():
        i = int(k)
        old = nodes[i] if i < len(nodes) else (0.0, 0.0, 0.0)
        p = [float(xyz[0]), float(xyz[1]),
             float(xyz[2]) if len(xyz) > 2 else float(old[2])]
        if i >= base:
            added[i - base] = p
        else:
            moved[str(i)] = p
    entry['added'] = added
    if 'dropped' in payload:
        entry['dropped'] = sorted({int(i) for i in payload['dropped']})
    for key in ('cut_edges', 'added_edges'):
        if key in payload:
            entry[key] = sorted({(min(int(a), int(b)), max(int(a), int(b)))
                                 for a, b in payload[key]})
            entry[key] = [list(e) for e in entry[key]]
    save(cell, entry)
    _refresh_nodes(cell, entry)
    return {'ok': True, 'moved': len(moved), 'added': len(added),
            'dropped': len(entry.get('dropped', []))}


def _refresh_nodes(cell, entry):
    """Update the cached bake's pathgrid in place after a save.

    Dropping the whole entry would re-parse every NIF in the cell on the next
    request -- seconds of work to answer an edit that cannot have changed one
    triangle of collision.
    """
    cached = _CACHE.get(cell)
    if cached is None:
        return
    nodes, edges = placed_nodes(cell, entry=entry)
    cached['nodes'] = [[round(p[0], 1), round(p[1], 1), round(p[2], 1)]
                       for p in nodes]
    cached['edges'] = [list(e) for e in edges]
    cached['moved'] = sorted(int(k) for k in entry.get('moved', {}))
    cached['dropped'] = sorted(entry.get('dropped', []))


def _edge_crosses(nodes, a, b, occ, step=32.0):
    """True if edge a-b leaves the authored mesh anywhere along its length."""
    pa, pb = nodes[a], nodes[b]
    d = max(abs(pb[0] - pa[0]), abs(pb[1] - pa[1]))
    n = max(1, int(d / step))
    for i in range(n + 1):
        f = i / float(n)
        x, y = pa[0] + (pb[0] - pa[0]) * f, pa[1] + (pb[1] - pa[1]) * f
        if (int(x // 64.0), int(y // 64.0)) not in occ:
            return True
    return False


def _occ_for(entry):
    """Cached occupancy grid of a cell's authored mesh.

    Rasterising it costs more than the scoring that follows, and it never
    changes while a cell is open -- the answer key is fixed.
    """
    ck = ('occ', entry['authored_cell'])
    if ck not in _CACHE:
        averts, atris = load_authored(entry['authored_esm'],
                                      entry['authored_cell'])
        _CACHE[ck] = occupancy(averts, atris)
    return _CACHE[ck]


def score(cell, edits=None):
    """Live node/edge quality, scoring UNSAVED edits when `edits` is given.

    The page sends its pending state so the readout tracks a drag without a
    round trip through the corpus file.
    """
    entry = load(cell)
    nodes, edges = placed_nodes(cell, entry=entry)
    dropped = set(entry.get('dropped', []))
    if edits:
        nodes, edges, dropped = _apply_pending(nodes, edges, edits)
    occ = _occ_for(entry)
    off = [i for i, p in enumerate(nodes)
           if i not in dropped
           and (int(p[0] // 64.0), int(p[1] // 64.0)) not in occ]
    bad = [[a, b] for (a, b) in edges
           if a not in dropped and b not in dropped
           and _edge_crosses(nodes, a, b, occ)]
    return {'off_nodes': off, 'bad_edges': bad,
            'n_nodes': len(nodes), 'n_edges': len(edges)}


def _apply_pending(nodes, edges, edits):
    """Overlay the page's unsaved edits on the stored `(nodes, edges)`."""
    nodes = [list(p) for p in nodes]
    for p in (edits.get('added') or []):
        nodes.append([float(p[0]), float(p[1]), float(p[2])])
    for k, xyz in (edits.get('moved') or {}).items():
        i = int(k)
        if 0 <= i < len(nodes):
            nodes[i] = [float(xyz[0]), float(xyz[1]),
                        float(xyz[2]) if len(xyz) > 2 else nodes[i][2]]
    dropped = {int(i) for i in (edits.get('dropped') or [])}
    cut = {(min(int(a), int(b)), max(int(a), int(b)))
           for a, b in (edits.get('cut_edges') or [])}
    out = [(a, b) for (a, b) in edges if (min(a, b), max(a, b)) not in cut]
    have = {(min(a, b), max(a, b)) for (a, b) in out}
    for a, b in (edits.get('added_edges') or []):
        a, b = int(a), int(b)
        k = (min(a, b), max(a, b))
        if k not in have and a < len(nodes) and b < len(nodes):
            have.add(k)
            out.append((a, b))
    return nodes, out, dropped


#: Export whose cells the mesh editor opens when the page names none.
DEFAULT_PLUGIN = os.path.basename(DEFAULT_EXPORT)


def _routes():
    """`(GET, POST)` endpoint tables, each `{path: fn(params[, payload])}`."""
    get = {
        '/cells': lambda q: cells(),
        '/plugins': lambda q: plugins(),
        '/plugin_cells': lambda q: plugin_cells(
            q.get('plugin', DEFAULT_PLUGIN), q.get('q', '')),
        '/mesh': lambda q: mesh_bake(q.get('plugin', DEFAULT_PLUGIN),
                                     q.get('cell', '')),
        '/geometry': lambda q: bake(q.get('cell', '')),
        '/score': lambda q: score(q.get('cell', '')),
    }
    post = {
        '/save': lambda q, p: apply_edits(q.get('cell', ''), p),
        '/score': lambda q, p: score(q.get('cell', ''), p),
        '/mesh_save': lambda q, p: mesh_save(q.get('plugin', DEFAULT_PLUGIN),
                                             q.get('cell', ''), p),
    }
    return get, post


_GET_ROUTES, _POST_ROUTES = _routes()


class Handler(BaseHTTPRequestHandler):
    """Serves the editor page and the geometry/edit JSON endpoints."""

    def log_message(self, fmt, *args):
        """Quiet: one line per request would bury the startup banner."""

    def _send(self, body, ctype='application/json'):
        """Write one response with the right headers."""
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self):
        """Serve the editor page itself."""
        with open(_PAGE, encoding='utf-8') as fh:
            self._send(fh.read(), 'text/html; charset=utf-8')

    def do_GET(self):
        """Route the page, cell lists, geometry and the live score."""
        path, _, query = self.path.partition('?')
        if path in ('/', '/index.html'):
            self._page()
            return
        route = _GET_ROUTES.get(path)
        if route is None:
            self.send_error(404)
            return
        self._send(route(query_params(query)))

    def do_POST(self):
        """Score pending edits, or commit them to a corpus."""
        path, _, query = self.path.partition('?')
        route = _POST_ROUTES.get(path)
        if route is None:
            self.send_error(404)
            return
        n = int(self.headers.get('Content-Length') or 0)
        payload = json.loads(self.rfile.read(n) or b'{}')
        self._send(route(query_params(query), payload))


def main():
    """CLI: serve the editor until interrupted."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args()
    found = cells()
    if not found:
        print('no corpus cells in %s -- run `transplant.py fit` first' % CORPUS)
        return 1
    print('loading the audit index (once, ~10s) ...')
    index_for(load(found[0]).get('export', DEFAULT_EXPORT))
    url = 'http://127.0.0.1:%d/' % a.port
    print('transplant editor: %s\n  cells: %s' % (url, ', '.join(found)))
    if not a.no_browser:
        webbrowser.open(url)
    HTTPServer(('127.0.0.1', a.port), Handler).serve_forever()
    return 0


if __name__ == '__main__':
    sys.exit(main())
