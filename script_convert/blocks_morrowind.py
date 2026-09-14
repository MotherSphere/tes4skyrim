"""
TES3 script blocks: one implicit body, not a typed event.

A TES4 script names the event a block answers (`begin GameMode`,
`begin OnActivate`) and `BLOCK_MAP` turns that name into a Papyrus event. TES3
has no such vocabulary: a script opens `begin <its own name>` and the body runs
every frame while the object is loaded, which is exactly what `gamemode` means.

The block type therefore carries the SCRIPT NAME, so it can never match
`BLOCK_MAP` and `assemble.events` dropped every TES3 block body and all --
measured over TR_Mainland.esm, 3,569 of 3,569 blocks dropped.

See: docs/commentary/script_convert_morrowind.md#implicit-blocks
"""

#: The TES4 block type a TES3 body behaves as: run every frame while loaded.
TES3_BLOCK_TYPE = 'gamemode'


def is_implicit_block(btype: str, filter_text: str, script_name: str) -> bool:
    """Whether this block is a TES3 body rather than a typed TES4 block.

    A TES3 `begin` names the script itself; a quoted name lexes as a string and
    lands in the filter instead, leaving the type empty. Either way the name is
    the script's own, which no TES4 block type ever is.
    See: docs/commentary/script_convert_morrowind.md#implicit-blocks
    """
    name = (script_name or '').strip().lower()
    if not name:
        return False
    if btype:
        return btype.strip().lower() == name
    return filter_text.strip().strip('"').lower() == name
