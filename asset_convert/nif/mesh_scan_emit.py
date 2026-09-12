"""Emit mesh-scan fragments for the NIFs the converter writes.

Split out of nif_converter: the import pipeline's bounds/collision scan is a
second parse of meshes this stage already produced, and these helpers hand it
the answer instead.  Keeping them here leaves the converter a call site.

See: docs/commentary/tes5_import_pipeline.md#producer-emitted-mesh-entries
"""

import os
import struct

from asset_convert.collision.collision_extract import (bounds_from_data,
                                                       collision_from_data,
                                                       physics_flags_from_data)
from asset_convert.collision.mesh_scan_fragments import (record_alias,
                                                         record_mesh_entry,
                                                         record_removal)

#: Vector ARRAYS whose values reach the collision soup unquantized.
_VECTOR_ARRAYS = (('bhkConvexVerticesShape', 'vertices'),
                  ('bhkCompressedMeshShapeData', 'big_verts'))

#: Single vector FIELDS on the same path, by owning block class.
_VECTOR_FIELDS = (('bhkBoxShape', 'dimensions'),
                  ('bhkSphereShape', 'translation'),
                  ('bhkCapsuleShape', 'first_point'),
                  ('bhkCapsuleShape', 'second_point'),
                  ('bhkRigidBody', 'translation'),
                  ('bhkRigidBodyT', 'translation'))

#: 4x4 transform MATRICES applied to a primitive's vertices.
_MATRIX_FIELDS = (('bhkConvexTransformShape', 'transform'),
                  ('bhkTransformShape', 'transform'))

#: Scalar float fields that scale or inflate a primitive.
_SCALAR_FIELDS = (('bhkCapsuleShape', 'radius'),
                  ('bhkCapsuleShape', 'radius_1'),
                  ('bhkCapsuleShape', 'radius_2'),
                  ('bhkSphereShape', 'radius'))

#: Cell names of a pyffi 4x4 matrix, row-major.
_MATRIX_CELLS = tuple('m_%d%d' % (r, c)
                      for r in range(1, 5) for c in range(1, 5))


def _f32(value):
    """`value` rounded to the float32 precision a NIF float field stores."""
    return struct.unpack('<f', struct.pack('<f', value))[0]


def _quantize_collision_floats(data):
    """Round the collision graph's float vectors to what the FILE will hold.

    pyffi keeps float32 fields at full Python precision until serialization, so
    a soup read from the live graph differs from one read back from disk in the
    low bits -- and a convex hull turns that into different simplices entirely.
    Rounding first makes the two agree exactly.
    See: docs/commentary/tes5_import_pipeline.md#producer-emitted-mesh-entries
    """
    for block in data.blocks:
        name = type(block).__name__
        for cls, attr in _VECTOR_ARRAYS:
            if name == cls:
                for vec in getattr(block, attr, ()) or ():
                    _round_vector(vec)
        for cls, attr in _VECTOR_FIELDS:
            if name == cls:
                _round_vector(getattr(block, attr, None))
        for cls, attr in _MATRIX_FIELDS:
            if name == cls:
                _round_matrix(getattr(block, attr, None))
        for cls, attr in _SCALAR_FIELDS:
            if name == cls and hasattr(block, attr):
                setattr(block, attr, _f32(getattr(block, attr)))


def _round_matrix(mat) -> None:
    """Round every cell of a 4x4 transform to float32."""
    if mat is None:
        return
    for cell in _MATRIX_CELLS:
        if hasattr(mat, cell):
            setattr(mat, cell, _f32(getattr(mat, cell)))


def _round_vector(vec) -> None:
    """Round one vector's x/y/z (and w, when present) to float32."""
    if vec is None:
        return
    vec.x, vec.y, vec.z = _f32(vec.x), _f32(vec.y), _f32(vec.z)
    if hasattr(vec, 'w'):
        vec.w = _f32(vec.w)


def mesh_scan_key(model_rel):
    """Cache key for a model path: lowercase, forward slashes, or None."""
    if model_rel is None:
        return None
    return model_rel.replace(os.sep, '/').lower()


def record_scan_entry(data, model_rel):
    """Emit the bounds/collision fragment for a mesh written from *data*.

    Called at the write point, AFTER the post-passes have finished mutating
    the tree, so the analysis matches a re-parse of the bytes on disk.
    """
    key = mesh_scan_key(model_rel)
    if key is None:
        return
    try:
        bounds = bounds_from_data(data)
        physics = physics_flags_from_data(data) if bounds is not None else 0
        _quantize_collision_floats(data)
        collision = collision_from_data(data)
    except Exception:
        return
    record_mesh_entry(key, bounds, physics, collision)


def record_scan_removal(model_rel):
    """Drop the entry for a file the variant plan deleted."""
    key = mesh_scan_key(model_rel)
    if key is not None:
        record_removal(key)


def record_scan_alias(model_rel, source_rel):
    """Publish *model_rel*'s entry as a byte-identical copy of *source_rel*."""
    key = mesh_scan_key(model_rel)
    src = mesh_scan_key(source_rel)
    if key is not None and src is not None:
        record_alias(key, src)
