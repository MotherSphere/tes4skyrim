"""
Morrowind groundcover plugins as real Skyrim grass.

Morrowind has no grass record. Groundcover mods place one static per clump --
2.73M of them in Aesthesia's Tamriel Rebuilt set -- because the engine offers
nothing else. Converting those literally yields millions of STAT references
Skyrim renders individually, with no instancing, LOD or wind.

Skyrim instead scatters grass procedurally per LANDSCAPE TEXTURE: a GRAS record
names the model, and an LTEX names the grasses that grow on it. So the
placements are inverted into that model -- sample the land texture under every
clump, tally which grasses grow on which texture, and emit the GRAS plus the
LTEX bindings that reproduce the distribution.

The terrain being sampled usually belongs to the MASTER: a groundcover plugin
ships cells and statics only, never LAND.

See: docs/commentary/tes4_export_morrowind.md#groundcover-as-grass
"""

import os
from collections import Counter, defaultdict

from .morrowind_ids import remap_form_id
from .morrowind_world import TES4_CELL_SIZE
from .record_types.common import escape_value

#: Model-path prefix every groundcover static shares -- the authored marker.
GRASS_MODEL_PREFIX = 'grass' + chr(92)

#: Vertices in one TES4 LAND quadrant's alpha grid.
QUAD_VERTS_TOTAL = 17 * 17

#: Skyrim saturates grass density well below the record byte's 0-255.
MAX_DENSITY = 100

#: Side of the LAND quad the planter scatters over, in world units.
QUAD_SIZE = 2048.0

#: iMinGrassSize in Skyrim.ini; the planter caps its grid step at it.
SKYRIM_MIN_GRASS_SIZE = 20.0

#: Density each model's jitter cell is solved for; mid vanilla (3-23).
TARGET_DENSITY = 14.0

#: Bounds on the solved jitter cell; the floor is convert_GRAS's Oblivion-parity clamp, which rescales anything below.
MIN_POSITION_RANGE = 80.0
MAX_POSITION_RANGE = 140.0

#: ColorRange and WavePeriod every vanilla grass sets; Morrowind has neither.
VANILLA_COLOR_RANGE = 0.2
VANILLA_WAVE_PERIOD = 120.0

#: The slope ceiling vanilla grass uses; 90 would grow it up cliff faces.
_MAX_SLOPE = 45

#: Placements a (texture, model) pairing needs before it counts as authored.
MIN_PAIR_SUPPORT = 8

#: Grasses the engine plants per texture: iMaxGrassTypesPerTexure's default.
MAX_GRASSES_PER_TEXTURE = 2

#: Keys an LTEX override never repeats; a splice of these re-mints the TXST.
_LTEX_OWN_KEYS = frozenset({'Signature', 'FormID', 'RecordFlags',
                            'ICON', 'TextureIndex'})

#: Scales kept per model to characterise its spread.
_SCALE_SAMPLE = 4096

#: Uniform Scaling + Fit to Slope, the flags all 27 vanilla GRAS records set.
_GRAS_FLAGS = 6

#: Slope floor vanilla grass accepts, in degrees.
_MIN_SLOPE = 0


def is_grass_model(model: str) -> bool:
    """Whether a static's model path marks it as groundcover."""
    return bool(model) and model.replace('/', chr(92)).lower().startswith(
        GRASS_MODEL_PREFIX)


def _record_blocks(path: str):
    """Each record in an export dump as a dict of its scalar fields.

    Bulk vertex arrays are skipped by prefix rather than parsed: they are ~97%
    of a LAND dump's bytes and name no texture.
    """
    if not os.path.isfile(path):
        return
    fields = {}
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if line.startswith(('VHGT', 'VNML', 'VCLR')):
                continue
            if line.startswith('---RECORD_END---'):
                if fields:
                    yield fields
                fields = {}
                continue
            key, sep, value = line.rstrip('\n').partition('=')
            if sep:
                fields[key] = value


def _cell_grids(export_dir: str, remap: dict = None) -> dict:
    """Exterior cell FormID -> its (X, Y) grid, from a master's CELL dump."""
    out = {}
    for rec in _record_blocks(os.path.join(export_dir, 'CELL.txt')):
        x, y = rec.get('XCLC.X'), rec.get('XCLC.Y')
        fid = remap_form_id(rec.get('FormID', ''), remap)
        if x is not None and y is not None and fid:
            out[fid.upper()] = (int(x), int(y))
    return out


def _read_land_layers(rec: dict) -> dict:
    """One LAND record's layers, folded into per-quadrant texture coverage."""
    out = {}
    for i in range(int(rec.get('LayerCount', 0) or 0)):
        kind = rec.get('Layer[%d].Type' % i, '')
        if kind == 'BASE':
            quad = int(rec.get('Layer[%d].BTXT.Quadrant' % i, 0) or 0)
            out['BTXT.%d' % quad] = rec.get('Layer[%d].BTXT.Texture' % i, '')
        elif kind == 'ALPHA':
            quad = int(rec.get('Layer[%d].ATXT.Quadrant' % i, 0) or 0)
            painted = int(rec.get('Layer[%d].VTXTCount' % i, 0) or 0)
            out.setdefault('ATXT.%d' % quad, []).append(
                (rec.get('Layer[%d].ATXT.Texture' % i, ''),
                 painted / float(QUAD_VERTS_TOTAL)))
    return out


def _quadrant_texture(layers: dict, quadrant: int) -> str:
    """The FormID of the texture covering most of one LAND quadrant.

    The BASE layer covers the whole quadrant; an ALPHA layer covers only the
    vertices it lists, so it wins only where it is painted over most of them.
    """
    best = layers.get('BTXT.%d' % quadrant, '')
    best_share = 0.5
    for texture, share in layers.get('ATXT.%d' % quadrant, ()):
        if share > best_share:
            best, best_share = texture, share
    return best


def master_texture_grid(export_dir: str, remap: dict = None) -> dict:
    """TES4 cell grid -> the dominant LTEX FormID over each of its quadrants.

    Reads the master's LAND dump, already split into Oblivion cells, so no
    VTEX de-swizzling is needed.  Every id is re-keyed through `remap` into
    THIS plugin's master list, or the binding names a record the game
    resolves to a different file.
    See: docs/commentary/tes4_export_morrowind.md#groundcover-as-grass
    """
    grids = _cell_grids(export_dir, remap)
    out = {}
    for rec in _record_blocks(os.path.join(export_dir, 'LAND.txt')):
        grid = grids.get((remap_form_id(rec.get('ParentCELL', ''), remap)
                          or '').upper())
        if grid is None:
            continue
        layers = _read_land_layers(rec)
        quads = [remap_form_id(_quadrant_texture(layers, q), remap) or ''
                 for q in range(4)]
        if any(quads):
            out[grid] = quads
    return out


def master_ltex_fields(export_dir: str, remap: dict = None) -> dict:
    """LTEX FormID -> the master fields an override repeats verbatim.

    Everything the diff must NOT see is left out (`_LTEX_OWN_KEYS`, plus the
    master's own grass -- repeating a key makes the reader fold both values
    into a LIST and the diff cannot order it), so the only authored change is
    the grass run and the master's own TNAM survives untouched.
    See: docs/commentary/tes4_export_morrowind.md#groundcover-as-grass
    """
    out = {}
    for rec in _record_blocks(os.path.join(export_dir, 'LTEX.txt')):
        fid = remap_form_id(rec.get('FormID', ''), remap)
        if fid:
            out[fid.upper()] = {
                k: v for k, v in rec.items()
                if k not in _LTEX_OWN_KEYS and not k.startswith('Grass')}
    return out


def _sample(grid_map: dict, pos_x: float, pos_y: float) -> str:
    """The LTEX FormID of the ground under one world position, or ''."""
    grid = (int(pos_x // TES4_CELL_SIZE), int(pos_y // TES4_CELL_SIZE))
    quads = grid_map.get(grid)
    if not quads:
        return ''
    half = TES4_CELL_SIZE / 2.0
    local_x = pos_x - grid[0] * TES4_CELL_SIZE
    local_y = pos_y - grid[1] * TES4_CELL_SIZE
    return quads[(0 if local_x < half else 1) + (0 if local_y < half else 2)]


class GrassTally:
    """Groundcover placements, accumulated per (land texture, grass model).

    Fed one reference at a time during the cell walk, so the 2.73M placements
    are never held in memory at once.
    """

    def __init__(self, grid_map: dict):
        """Start empty over a master's texture grid."""
        self.grid_map = grid_map
        self.quads = Counter(tex.upper() for quads in grid_map.values()
                             for tex in quads if tex)
        self.pairs = Counter()
        self.scales = defaultdict(list)
        self.unplaced = 0
        self._bindings = None

    def add(self, model_key: str, pos: tuple, scale: float) -> None:
        """Note one groundcover clump against the texture beneath it."""
        texture = _sample(self.grid_map, pos[0], pos[1])
        if not texture:
            self.unplaced += 1
            return
        self.pairs[(texture.upper(), model_key)] += 1
        if len(self.scales[model_key]) < _SCALE_SAMPLE:
            self.scales[model_key].append(scale)

    def bindings(self) -> dict:
        """Land texture FormID -> {model: clumps it plants} on that texture.

        The engine plants only the first MAX_GRASSES_PER_TEXTURE grasses a
        texture names, so the commonest models on a texture are kept and
        absorb the rest of its clumps in proportion: the texture ends up as
        thick as the author made it, with its dominant grasses.
        See: docs/commentary/tes4_export_morrowind.md#groundcover-as-grass
        """
        if self._bindings is not None:
            return self._bindings
        by_texture = defaultdict(Counter)
        for (texture, model), count in self.pairs.items():
            by_texture[texture][model] = count
        out = {}
        for texture, counts in by_texture.items():
            kept = [(m, c) for m, c in counts.most_common(
                MAX_GRASSES_PER_TEXTURE) if c >= MIN_PAIR_SUPPORT]
            share = sum(c for _, c in kept)
            if share:
                total = sum(counts.values())
                out[texture] = {m: c * total / share for m, c in kept}
        self._bindings = out
        return self._bindings

    def _per_quad(self, texture: str, model_key: str) -> float:
        """Clumps of one model per LAND quad of one texture."""
        planted = self.bindings()[texture][model_key]
        return max(0.01, planted / max(1, self.quads[texture]))

    def position_range(self, texture: str, model_key: str) -> float:
        """The jitter cell that puts this pairing's density in vanilla range.

        See: docs/commentary/tes4_export_morrowind.md#groundcover-as-grass
        """
        solved = QUAD_SIZE * ((TARGET_DENSITY / MAX_DENSITY
                               / self._per_quad(texture, model_key)) ** 0.5)
        return max(MIN_POSITION_RANGE, min(MAX_POSITION_RANGE, solved))

    def density(self, texture: str, model_key: str) -> int:
        """The GRAS density reproducing this pairing's authored clump count.

        The planter lays n = min(2048/PositionRange, 2048/iMinGrassSize)
        candidates per quad side and keeps each with probability Density%, so
        matching the source count is a division.
        See: docs/commentary/asset_convert_terrain.md#grass-placement-parity
        """
        side = min(QUAD_SIZE / self.position_range(texture, model_key),
                   QUAD_SIZE / SKYRIM_MIN_GRASS_SIZE)
        share = self._per_quad(texture, model_key) / (side * side) * MAX_DENSITY
        return max(1, min(MAX_DENSITY, round(share)))

    def height_range(self, model_key: str) -> float:
        """The spread of authored scales on one grass model."""
        values = self.scales.get(model_key) or [1.0]
        return max(values) - min(values)


def grass_records(tally: GrassTally, models: dict, resolve) -> list:
    """The GRAS records one plugin's groundcover implies, as (FormID, lines).

    One record per (texture, model) pairing, so each texture carries the
    density its author gave it. `models` maps each grass static's record id
    to its model path; `resolve(model, texture)` mints the FormID, keyed on
    the authored ids so they hold still across runs.
    """
    out = []
    for texture in sorted(tally.bindings()):
        for model_key in sorted(tally.bindings()[texture]):
            path = models.get(model_key)
            if not path:
                continue
            out.append((resolve(model_key, texture), [
                f'EditorID={model_key}_{texture}',
                f'Model.MODL={escape_value(path)}',
                f'DATA.Density={tally.density(texture, model_key)}',
                f'DATA.MinSlope={_MIN_SLOPE}',
                f'DATA.MaxSlope={_MAX_SLOPE}',
                'DATA.UnitFromWaterAmount=0',
                'DATA.UnitFromWaterType=0',
                f'DATA.PositionRange='
                f'{tally.position_range(texture, model_key):.6f}',
                f'DATA.HeightRange={tally.height_range(model_key):.6f}',
                f'DATA.ColorRange={VANILLA_COLOR_RANGE:.6f}',
                f'DATA.WavePeriod={VANILLA_WAVE_PERIOD:.6f}',
                f'DATA.Flags={_GRAS_FLAGS}',
            ]))
    return out


def ltex_grass_lines(bindings: dict, texture: str, resolve,
                     fields: dict = None) -> list:
    """One land texture re-emitted with its grasses bound.

    `fields` is the master's own record, repeated verbatim so the override
    changes the grass run and nothing else.
    """
    grasses = sorted(bindings.get(texture) or ())
    if not grasses:
        return []
    lines = [f'{k}={v}' for k, v in (fields or {}).items()]
    lines.append(f'GrassCount={len(grasses)}')
    lines.extend(f'Grass[{i}]={resolve(model, texture)}'
                 for i, model in enumerate(grasses))
    return lines
