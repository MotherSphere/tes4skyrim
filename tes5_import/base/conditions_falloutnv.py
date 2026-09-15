"""FO3/FNV CTDA fields that TES4's 24-byte layout does not carry.

A Fallout CTDA is 28 bytes: TES4's 20 shared bytes, then an explicit Run On
u32 and a Reference u32 in place of TES4's unused tail.  Its function indices
follow Fallout's own table, so they are rewritten to Skyrim's before any
index-keyed lookup.

See: docs/commentary/tes5_import_conditions.md#fallout-ctda
"""

import struct

from ..generated.ctda_fnv_remap import FNV_FUNC_ABSENT, FNV_FUNC_REMAP

#: A CTDA at least this long carries Fallout's Run On / Reference tail.
FALLOUT_CTDA_SIZE = 28

#: GetDisposition: absent in Skyrim, but evaluated at a fixed tier by convert_ctda.
_GET_DISPOSITION = 76

#: Fallout Run On values: Subject, Target, Reference, Combat Target, Linked Ref.
_RUN_ON_TARGET = 1
_RUN_ON_REFERENCE = 2


def fallout_function(func_idx: int) -> 'int | None':
    """The Skyrim index for a Fallout condition function, or None if it has none."""
    if func_idx in FNV_FUNC_ABSENT and func_idx != _GET_DISPOSITION:
        return None
    return FNV_FUNC_REMAP.get(func_idx, func_idx)


def fallout_run_on(raw: bytes, remap) -> tuple:
    """(is_target, run_on, reference) from the Fallout tail.

    Run On = Target is reported as `is_target` so the caller applies the
    same Say-topic retargeting it gives TES4's run-on-target flag; every
    other Run On passes through with its reference load-order remapped.
    """
    run_on, reference = struct.unpack_from('<II', raw, 20)
    if run_on == _RUN_ON_TARGET:
        return True, 0, 0
    if run_on == _RUN_ON_REFERENCE:
        reference = remap(reference)
    return False, run_on, reference
