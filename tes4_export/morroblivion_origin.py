"""How far a Morroblivion replacement mesh sits from where Morrowind seated the
vanilla one, so placed references can be compensated.

Morrowind rests an object on its `RootCollisionNode` when it has one, else on
its render geometry; the converted mesh is seated by render geometry alone. A
plugin's authored Z was measured against the vanilla mesh, so wherever
Morroblivion moved the render frame WITHOUT landing it on the old resting
plane, every reference of that record hovers by the remainder.

Measured over the 91 meshes Tamriel Data records name: 68 keep the vanilla
render frame, 2 re-seat cleanly, 16 replace the geometry outright, and 5 are
partial re-seats that hover — `o\\contain_barrel10.nif` by 27.86, the rest
under 2.2.

See: docs/commentary/tes4_export_morrowind.md#morroblivion-origin-shift
"""

import os

from asset_convert.nif.pyffi_monkey_patch import apply_patches
from pyffi.formats.nif import NifFormat

from asset_convert.sources.morrowind_assets import find_archived_mesh

#: Below this a difference is authoring noise, not a displaced mesh.
_MIN_SHIFT = 0.5


def _collision_ids(root) -> set:
    """ids of every block under a RootCollisionNode — Morrowind's resting shape."""
    hidden = set()
    for block in root.tree():
        if type(block).__name__ == 'RootCollisionNode':
            hidden.update(id(child) for child in block.tree())
    return hidden


def _lowest(node, acc: float, collision: set, found: dict) -> None:
    """Record the lowest render and collision vertex at or below `node`.

    Node translations accumulate down the tree, so a shape's resting plane is
    its own vertices plus every parent's offset.
    """
    offset = getattr(node, 'translation', None)
    depth = acc + (offset.z if offset is not None else 0.0)
    verts = getattr(getattr(node, 'data', None), 'vertices', None)
    if isinstance(node, NifFormat.NiTriBasedGeom) and verts:
        slot = 'coll' if id(node) in collision else 'rend'
        low = depth + min(v.z for v in verts)
        found[slot] = low if found[slot] is None else min(found[slot], low)
    for child in getattr(node, 'children', None) or []:
        if child is not None:
            _lowest(child, depth, collision, found)


def _bottoms(path) -> tuple:
    """(render bottom, collision bottom) in model space; None where absent."""
    apply_patches()
    data = NifFormat.Data()
    with open(path, 'rb') as handle:
        data.read(handle)
    found = {'rend': None, 'coll': None}
    for root in data.roots:
        _lowest(root, 0.0, _collision_ids(root), found)
    return found['rend'], found['coll']


def origin_shift(vanilla_path, replacement_path) -> float:
    """How far the replacement hovers above where Morrowind seated the original.

    Returns 0.0 when either mesh is unreadable, when the replacement keeps the
    vanilla render frame (nothing moved), or when the remainder is noise.
    """
    try:
        van_rend, van_coll = _bottoms(vanilla_path)
        rep_rend, _rep_coll = _bottoms(replacement_path)
    except Exception:
        return 0.0
    if rep_rend is None or van_rend is None or van_coll is None:
        return 0.0
    if abs(rep_rend - van_rend) < _MIN_SHIFT:
        return 0.0
    shift = rep_rend - van_coll
    return shift if abs(shift) >= _MIN_SHIFT else 0.0


class OriginShifts:
    """Measured shift per (vanilla mesh, replacement mesh), computed once."""

    def __init__(self, export_root: str, mesh_roots=()):
        """Resolve replacements under `mesh_roots`, vanilla via `export_root`."""
        self._export_root = export_root
        self._roots = [str(r) for r in mesh_roots if r]
        self._cache = {}

    def _replacement_file(self, replacement: str):
        """The replacement mesh on disk, searched across the known trees."""
        rel = replacement.replace('/', os.sep).replace(chr(92), os.sep).lstrip(os.sep)
        for root in self._roots:
            path = os.path.join(root, rel)
            if os.path.isfile(path):
                return path
        return None

    def shift_for(self, vanilla: str, replacement: str) -> float:
        """Shift for one substitution, measured on first ask and cached."""
        key = (vanilla.lower(), replacement.lower())
        if key in self._cache:
            return self._cache[key]
        van = find_archived_mesh(self._export_root, vanilla)
        rep = self._replacement_file(replacement)
        value = 0.0
        if van and rep:
            value = origin_shift(str(van), rep)
        self._cache[key] = value
        return value
