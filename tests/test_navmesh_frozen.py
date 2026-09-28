"""Frozen navmesh patches: applying them over a generator, storing and unpinning them."""

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tes5_import.base import navmesh_pins as pins
from tes5_import.base.navmesh_frozen import apply_frozen, plan_area
from tools.cellview.bake import frozen_patch, merge_patches

#: A 3x3 vertex grid over (0..20)^2 at Z 0: four squares, eight triangles.
GRID = [(float(x), float(y), 0.0) for y in (0, 10, 20) for x in (0, 10, 20)]
GRID_TRIS = [(0, 1, 4), (0, 4, 3), (1, 2, 5), (1, 5, 4),
             (3, 4, 7), (3, 7, 6), (4, 5, 8), (4, 8, 7)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pts(verts, t):
    """Triangle `t` as a tuple of its three corner positions."""
    return tuple(verts[k] for k in t)


def _shapes(verts, tris):
    """The triangles as winding-free corner sets, for comparison."""
    return {frozenset(verts[k] for k in t) for t in tris}


def _area(verts, tris):
    """Total plan area of `tris`."""
    return sum(plan_area(_pts(verts, t)) for t in tris)


def _max_edge_owners(tris):
    """The most triangles any one edge has."""
    c = Counter(frozenset((t[k], t[(k + 1) % 3])) for t in tris for k in range(3))
    return max(c.values())


#: The bottom-left square re-cut on its other diagonal: what a human froze.
FLIPPED = [((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 10.0, 0.0)),
           ((10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0))]

#: The two generated triangles that square replaced.
REPLACED = [_pts(GRID, GRID_TRIS[0]), _pts(GRID, GRID_TRIS[1])]

#: A second patch far from the first, so unpinning one must leave it.
FAR = [((100.0, 100.0, 0.0), (110.0, 100.0, 0.0), (100.0, 110.0, 0.0))]


# ---------------------------------------------------------------------------
# Applying a patch
# ---------------------------------------------------------------------------

def test_an_unmoved_generator_yields_exactly_the_humans_mesh():
    """The replaced triangles go, the frozen ones go in, the rest is untouched.

    See: docs/commentary/tes5_import_navmesh.md#frozen-navmesh-patches
    """
    verts, tris, _l = apply_frozen(GRID, GRID_TRIS, [], FLIPPED, REPLACED)
    want = _shapes(GRID, GRID_TRIS[2:]) | {frozenset(t) for t in FLIPPED}
    assert _shapes(verts, tris) == want
    assert _max_edge_owners(tris) == 2


def test_a_moved_generator_is_refilled_around_the_frozen_triangles():
    """Frozen triangles stay exact; the uncovered rest of the removed floor is refilled.

    See: docs/commentary/tes5_import_navmesh.md#frozen-navmesh-patches
    """
    big = [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 20.0, 0.0), (0.0, 20.0, 0.0)]
    verts, tris, _l = apply_frozen(big, [(0, 1, 2), (0, 2, 3)], [],
                                   FLIPPED, REPLACED)
    assert {frozenset(t) for t in FLIPPED} <= _shapes(verts, tris)
    assert abs(_area(verts, tris) - 400.0) < 1e-6
    assert _max_edge_owners(tris) == 2


def test_a_patch_never_removes_another_storey():
    """A deck 200u above the patch keeps every triangle."""
    deck = [(x, y, 200.0) for (x, y, _z) in GRID]
    verts = GRID + deck
    tris = GRID_TRIS + [tuple(k + 9 for k in t) for t in GRID_TRIS]
    out_v, out_t, _l = apply_frozen(verts, tris, [], FLIPPED, REPLACED)
    assert _shapes(deck, GRID_TRIS) <= _shapes(out_v, out_t)


def test_a_deletion_alone_leaves_a_hole():
    """Voids with nothing frozen are ground the human removed; nothing refills it."""
    verts, tris, _l = apply_frozen(GRID, GRID_TRIS, [], [], REPLACED)
    assert abs(_area(verts, tris) - 300.0) < 1e-6


def test_a_sliver_the_human_replaced_is_claimed_whatever_its_size():
    """A generated sliver identical to a void goes, though it overlaps nothing."""
    verts = GRID + [(20.0, 20.0, 0.0), (20.0, 20.05, 0.0), (30.0, 20.0, 0.0)]
    tris = GRID_TRIS + [(9, 10, 11)]
    _v, out, _l = apply_frozen(verts, tris, [], [], [_pts(verts, (9, 10, 11))])
    assert len(out) == len(GRID_TRIS)


def test_ledges_follow_the_kept_triangles_and_drop_with_removed_ones():
    """A ledge on a removed triangle goes; one between kept triangles is renumbered."""
    ledges = [(0, 7, 50.0), (2, 7, 40.0)]
    _v, _t, out = apply_frozen(GRID, GRID_TRIS, ledges, FLIPPED, REPLACED)
    assert out == [(0, 5, 40.0)]


def test_no_patch_leaves_the_mesh_untouched():
    """An unpatched cell must be exactly what it was before patches existed."""
    verts, tris, _l = apply_frozen(GRID, GRID_TRIS, [], [], [])
    assert verts is GRID and tris is GRID_TRIS


# ---------------------------------------------------------------------------
# Building a patch from the editor's ops
# ---------------------------------------------------------------------------

def test_a_deletion_only_edit_freezes_nothing():
    """Deleting a triangle voids it; it never freezes the whole mesh."""
    frozen, voids = frozen_patch(GRID, GRID_TRIS, [{'op': 'del_tri', 'tri': 0}])
    assert frozen == [] and voids == [_pts(GRID, GRID_TRIS[0])]


def test_a_move_freezes_and_voids_every_triangle_on_that_vertex():
    """The moved corner's triangles are frozen as moved and voided as generated."""
    ops = [{'op': 'move_vert', 'v': 4, 'to': [11.0, 11.0, 0.0]}]
    frozen, voids = frozen_patch(GRID, GRID_TRIS, ops)
    assert len(frozen) == len(voids) == 6
    assert all((11.0, 11.0, 0.0) in t for t in frozen)


def test_a_re_edit_replaces_the_older_frozen_triangle():
    """An older frozen triangle the new edit voided is dropped; others stay."""
    frozen, voids = merge_patches(list(FLIPPED), REPLACED, [], [FLIPPED[0]])
    assert frozen == [FLIPPED[1]]
    assert voids == REPLACED + [FLIPPED[0]]


# ---------------------------------------------------------------------------
# The store
# ---------------------------------------------------------------------------

def _store(tmp_path, monkeypatch):
    """Point the pin store at a temp dir and clear its cache."""
    monkeypatch.setattr(pins, 'PINS', str(tmp_path))
    monkeypatch.setattr(pins, '_CACHE', {})


def test_patches_round_trip_and_restage_the_cell(tmp_path, monkeypatch):
    """Frozen and void rows read back as triangles and move the digest."""
    _store(tmp_path, monkeypatch)
    assert pins.digest('Nehrim.esm', 'Cell') == ''
    pins.save('Nehrim.esm', 'Cell', frozen=FLIPPED, voids=REPLACED)
    edits = pins.hand_edits_for('Nehrim.esm', 'cell')
    assert edits['frozen'] == FLIPPED and edits['voids'] == REPLACED
    assert pins.digest('Nehrim.esm', 'Cell')


def test_saving_a_patch_keeps_the_older_pins(tmp_path, monkeypatch):
    """A section left out of a save is left alone."""
    _store(tmp_path, monkeypatch)
    pins.save('Nehrim.esm', 'Cell', [(1.0, 2.0, 3.0)])
    pins.save('Nehrim.esm', 'Cell', frozen=FLIPPED, voids=REPLACED)
    assert pins.pins_for('Nehrim.esm', 'Cell') == [(1.0, 2.0, 3.0)]


def test_unpinning_removes_only_the_patch_at_the_point(tmp_path, monkeypatch):
    """The joined patch under the point goes; a separate patch stays."""
    _store(tmp_path, monkeypatch)
    pins.save('Nehrim.esm', 'Cell', frozen=FLIPPED + FAR, voids=REPLACED)
    _p, nf, nv = pins.remove_patch('Nehrim.esm', 'Cell', (3.0, 3.0, 0.0))
    assert (nf, nv) == (2, 2)
    assert pins.tris_for('Nehrim.esm', 'frozen', 'Cell') == FAR
    assert pins.tris_for('Nehrim.esm', 'voids', 'Cell') == []


def test_unpinning_a_whole_cell_clears_its_patches(tmp_path, monkeypatch):
    """No point removes every patch, and the digest goes back to empty."""
    _store(tmp_path, monkeypatch)
    pins.save('Nehrim.esm', 'Cell', frozen=FLIPPED + FAR, voids=REPLACED)
    pins.remove_patch('Nehrim.esm', 'Cell')
    assert pins.digest('Nehrim.esm', 'Cell') == ''
