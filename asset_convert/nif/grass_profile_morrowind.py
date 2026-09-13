"""
Wind weights for grass NIFs that ship none.

Skyrim's grass shader reads vertex-colour ALPHA as sway amplitude, gated by
`SLSF2_Vertex_Colors`. Oblivion and Fallout grass meshes already carry both, so
the shared profile never had to author them. MORROWIND meshes carry neither:
all 64 Aesthesia/TR models converted with `has_vertex_colors=False` and
`flags2=0x8011` against the working `0x8031` -- structurally valid, and
invisible in game.

The weights are derived from the geometry the way vanilla authors them,
measured on `tes4_brmediumgrassyellow01`: alpha 0 across the rooted base,
ramping with height to 0.3-0.47 at the tip.

See: docs/commentary/asset_convert_terrain.md#grass-conversion-record-invariants-shader
"""

#: Wind weight at a blade tip; vanilla tops out near 0.3-0.47, base pinned 0.
GRASS_MAX_WIND_WEIGHT = 0.45

#: Fraction of a blade's height that stays rooted (alpha 0).
GRASS_ROOT_FRACTION = 0.15


def add_wind_weights(data, nif_format):
    """Give every colourless grass shape vertex colours whose alpha is wind.

    A shape that already has them is left alone, so this is a no-op on the
    Oblivion and Fallout meshes the shared profile also runs over.
    """
    changed = False
    for block in data.blocks:
        if not isinstance(block, nif_format.NiTriShapeData):
            continue
        if block.has_vertex_colors or not block.num_vertices:
            continue
        zs = [v.z for v in block.vertices]
        low, span = min(zs), max(zs) - min(zs)
        block.has_vertex_colors = True
        block.vertex_colors.update_size()
        for i, vert in enumerate(block.vertices):
            colour = block.vertex_colors[i]
            colour.r = colour.g = colour.b = 1.0
            colour.a = _wind_weight(vert.z, low, span)
        changed = True
    return changed


def _wind_weight(height: float, low: float, span: float) -> float:
    """Sway amplitude for one vertex: 0 over the root, ramping to the tip."""
    if span <= 0.0:
        return 0.0
    share = (height - low) / span
    ramp = (share - GRASS_ROOT_FRACTION) / (1.0 - GRASS_ROOT_FRACTION)
    return max(0.0, min(1.0, ramp)) * GRASS_MAX_WIND_WEIGHT
