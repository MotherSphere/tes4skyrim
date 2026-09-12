"""Per-worldspace world-map cloud bank meshes.

WHY THIS EXISTS
---------------
Skyrim's world map draws a bank of cloud planes over the terrain.  The mesh is
chosen by a three-step fallback in the engine (SkyrimSE.exe, function at RVA
0x2c7e00):

    1. the PARENT worldspace's cloud model, when WRLD PNAM bit 2
       ("Use Map Data") is set;
    2. this worldspace's own WRLD `MODL` ("Cloud Model" in xEdit's TES5 WRLD
       definition, wbRStruct('Cloud Model', [wbGenericModel]));
    3. neither set (empty string) -> a HARDCODED default.  The tail of that
       function is

           cmp  byte ptr [rax], 0
           jne  <return it>
           lea  rax, [rip + 0x1397ef1]      ; -> 0x14165fd50

       and 0x14165fd50 is the string `Meshes\\Sky\\SkyrimWorldMapCloudBank.nif`.
       That is the ONLY cross-reference to it in the binary.

Oblivion has no world-map cloud layer to convert from, and vanilla Skyrim
authors no MODL either (0 of 35 uncompressed Skyrim.esm WRLDs carry one) -- so
every converted worldspace lands on step 3 and inherits a cloud bank sized for
Skyrim's Tamriel.

The bank is four flat XY sheets, each spanning +/-56902.8 local units at node
scale 8.0, i.e. 910,445 units (222 cells) across.  Against the worldspaces we
actually emit that ranges from roughly right to wildly oversized:

    Skyrim Tamriel      119 x  94 cells   ~1.9x cover   (what Bethesda tuned)
    TES4Tamriel         134 x 129 cells   ~1.7x
    NehrimWorldspace     92 x 101 cells   ~2.2x
    Arktwend             39 x  25 cells   ~5.7x
    ErothinFeste         16 x  26 cells   ~8.5x

so the small worldspaces get a cloud deck many times their landmass and it
reads as a solid overcast sheet rather than scattered banks.

WHAT THIS DOES
--------------
Emit one cloud-bank NIF per worldspace, scaled so the sheet covers that
worldspace's own NAM0/NAM9 rectangle at the same proportion Bethesda's covers
Skyrim's Tamriel, and point the WRLD's MODL at it.

Only the X/Y span is scaled.  The per-child Z offsets (0 / 1000 / 1500 / 12500)
are cloud ALTITUDES -- scaling them with the horizontal span would sink the
deck into the terrain on a small worldspace and launch it out of frame on a
large one.  Scaling is applied to each child node's `scale` (the four sheets
sit at scale 8.0 under a scale-1.0 BSFadeNode root), which leaves vertex data,
shader properties and the alpha-fade controllers untouched.
"""

import os

from pyffi.formats.nif import NifFormat

from asset_convert.game_paths import current_namespace

# Bethesda's bank: half-extent 56902.8 local * node scale 8.0.
_STOCK_NODE_SCALE = 8.0
_STOCK_HALF_EXTENT = 56902.8 * _STOCK_NODE_SCALE

# SIZE IS SET BY THE LAND, using Bethesda's own deck-to-land ratio.
#
# The stock deck spans 910445 and Skyrim's land is 487424 x 385024, so it is
# 1.868x that land on X and 2.365x on Y.  A converted worldspace's deck is
# given the same relationship to ITS land, per axis, so a portrait worldspace
# gets a portrait deck instead of a square one sized off its long side.
#
# The control that justifies this over the alternatives: feed it Skyrim's own
# land and it returns exactly 8.0 / 8.0, reproducing the shipped mesh.  A rule
# built instead from where the sheet's opaque band falls (t ~ 0.4-0.7 of the
# half-extent, measured area-weighted) has to explain why vanilla Skyrim's own
# land sits 2.7x outside its clear middle -- Bethesda lets the band cover
# Tamriel's unplayable border cells -- and any threshold that "fixes" that for
# Skyrim stops being measurable for a worldspace with no such border.
#
# For reference, measured on the stock sheet (area-weighted mean alpha per
# Chebyshev shell), in case a future change needs the band's real position:
#     t 0.0-0.2  0.08-0.13 clear | t 0.2-0.4  0.38-0.55 ramp
#     t 0.4-0.7  0.73-0.89 BAND  | t 0.7-0.9  0.47->0.33 fading out
_SKYRIM_LAND_X, _SKYRIM_LAND_Y = 487424.0, 385024.0
_DECK_OVER_LAND_X = (_STOCK_HALF_EXTENT * 2.0) / _SKYRIM_LAND_X   # 1.868
_DECK_OVER_LAND_Y = (_STOCK_HALF_EXTENT * 2.0) / _SKYRIM_LAND_Y   # 2.365

_SOURCE_REL = 'meshes\\sky\\skyrimworldmapcloudbank.nif'

def out_dir() -> str:
    """Where generated cloud banks go, relative to `meshes\\`.

    See: docs/commentary/asset_convert_texture.md#per-game-asset-namespace
    """
    return current_namespace() + '\\worldmapclouds'


def cloud_model_path(editor_id: str) -> str:
    """MODL value for a worldspace's generated cloud bank.

    MODL is relative to `meshes\\` and does NOT include it (vanilla writes e.g.
    `LoadScreenArt\\LoadScreenMRaltar01.nif`).  Mirrors what generate_cloud_bank
    writes on disk, so the record writer and the asset writer can never
    disagree about the name.
    """
    return '%s\\%s.nif' % (out_dir(), editor_id.lower())


def compute_axis_scales(reach_x: float, reach_y: float) -> tuple:
    """Per-axis (sx, sy) from Bethesda's own deck-to-land ratio.

    reach_x/reach_y: distance from the deck's CENTER to the farthest land edge
    on that axis.  Not half the land span -- the sheet is symmetric about its
    own center, so what matters is the longer side.

    Each axis is given the same deck-to-land relationship the stock sheet has
    to Skyrim's own land, so feeding this Skyrim's land reproduces the stock
    8.0 on both axes exactly.  That control is the reason to prefer this over
    a rule derived from where the sheet's opaque band happens to fall: any
    such rule has to explain why vanilla Skyrim violates it by 2.7x, and this
    one simply doesn't need to.

    Independent axes matter: the stock sheet is SQUARE, and a single node scale
    can only size it off the longer side, which on a portrait worldspace like
    Nehrim hangs more cloud across the short axis than the tall one needs.

    Returned as multipliers of the stock 56902.8 half-extent, i.e. directly
    comparable to the stock node scale of 8.0.
    """
    if reach_x <= 0.0 or reach_y <= 0.0:
        return (8.0, 8.0)
    sx = (reach_x * _DECK_OVER_LAND_X) / 56902.8
    sy = (reach_y * _DECK_OVER_LAND_Y) / 56902.8
    return (sx, sy)


_CELL = 4096.0


def framed_rect(nw_x, nw_y, se_x, se_y):
    """World-unit (min_x, min_y, max_x, max_y) of the region the map frames.

    MNAM stores the map's NW and SE CELL corners.  NW is the top-left, so it
    holds the smaller X and the LARGER Y; SE holds the larger X and the smaller
    Y.  Returned min/max are normalized so the caller never has to care.

    The SE cell is inclusive -- the map frames through the far edge of that
    cell, not up to its near edge -- so the span runs to (se_x + 1) cells.

    Returns None when the corners are missing or degenerate, so the caller can
    fall back to the NAM0/NAM9 rectangle.
    """
    if None in (nw_x, nw_y, se_x, se_y):
        return None
    min_x, max_x = sorted((float(nw_x), float(se_x) + 1.0))
    min_y, max_y = sorted((float(se_y), float(nw_y) + 1.0))
    if max_x <= min_x or max_y <= min_y:
        return None
    return (min_x * _CELL, min_y * _CELL, max_x * _CELL, max_y * _CELL)


def compute_center(min_x: float, min_y: float,
                   max_x: float, max_y: float) -> tuple:
    """World-unit (x, y) the sheet must sit over: the rectangle's midpoint.
    See: docs/commentary/asset_convert_terrain.md#world-map-cloud-bank-sizing
    """
    return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)


def _rescale_and_flatten(data, scales, keep: float, center=(0.0, 0.0)):
    """Stretch, center and flatten every sheet; `scales` is (sx, sy).

    Operates on the PARSED graph, never on raw bytes.  The stretch is baked
    into the vertices (node scale set to 1.0), node X/Y translations are SET
    to `center`, and `keep` is the fraction of each shape's Z relief retained
    about its MEDIAN z (0.0 = flat, 1.0 = untouched).  Vertex Z and the nodes'
    Z translations (cloud ALTITUDES) are preserved.  UVs are scaled by
    sx/_STOCK_NODE_SCALE so texel density stays constant in world units.

    Returns (n_nodes_scaled, n_shapes_flattened).
    See: docs/commentary/asset_convert_terrain.md#world-map-cloud-bank-sizing
    """
    sx, sy = scales
    scaled = flattened = 0
    for root in data.roots:
        for block in root.tree():
            if not isinstance(block, NifFormat.NiTriShape):
                continue
            block.scale = 1.0
            block.translation.x = center[0]
            block.translation.y = center[1]
            scaled += 1
            shape_data = block.data
            verts = shape_data.vertices if shape_data else None
            if not verts:
                continue
            for v in verts:
                v.x *= sx
                v.y *= sy

            uv_sets = getattr(shape_data, 'uv_sets', None)
            if uv_sets:
                fu = sx / _STOCK_NODE_SCALE
                fv = sy / _STOCK_NODE_SCALE
                for uvs in uv_sets:
                    for uv in uvs:
                        uv.u *= fu
                        uv.v *= fv
            if keep < 1.0:
                zs = sorted(v.z for v in verts)
                mid = zs[len(zs) // 2]
                for v in verts:
                    v.z = mid + (v.z - mid) * keep
                flattened += 1
            shape_data.update_center_radius()
    return scaled, flattened


def generate_cloud_bank(editor_id: str, width: float, height: float,
                        out_root: str, flatten: float = 0.0,
                        center=(0.0, 0.0), land_rect=None,
                        write: bool = True) -> str:
    """Write a scaled, centered cloud bank for one worldspace; return its MODL path.

    land_rect: (min_x, min_y, max_x, max_y) of the worldspace's REAL LAND in
    world units; supersedes width/height, which is legacy span-based sizing.
    out_root: the plugin's output folder (the one that holds `meshes\\`).
    center: world-unit (x, y) the deck is centered on.
    write: False validates and returns the MODL path without writing a file.

    Returns None when the source mesh is unavailable or its layout is not the
    one verified against, so the caller omits MODL and the engine falls back
    to its own default rather than a broken model reference.
    See: docs/commentary/asset_convert_terrain.md#world-map-cloud-bank-sizing
    """
    from asset_convert.sources.skyrim_assets import get_asset_bytes
    from asset_convert.nif.sse_nif import read_nif

    raw = get_asset_bytes(_SOURCE_REL)
    if not raw:
        return None

    data = read_nif(raw)
    if land_rect:
        mnx, mny, mxx, mxy = land_rect
        reach_x = max(abs(mnx - center[0]), abs(mxx - center[0]))
        reach_y = max(abs(mny - center[1]), abs(mxy - center[1]))
    else:
        reach_x, reach_y = width / 2.0, height / 2.0
    scaled, _ = _rescale_and_flatten(data,
                                     compute_axis_scales(reach_x, reach_y),
                                     flatten, center)
    if scaled == 0:
        return None

    rel = cloud_model_path(editor_id)
    if not write:
        return rel
    # MODL omits the `meshes\` prefix; the file on disk needs it.
    dest = os.path.join(out_root, 'meshes', *rel.split('\\'))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, 'wb') as fh:
        data.write(fh)
    return rel
