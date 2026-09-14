# Morrowind scripts

**Code:** `script_convert/blocks_morrowind.py`

What TES3 script conversion does differently from TES4, and why.

## <a id="implicit-blocks"></a>A TES3 script is one implicit block

A TES4 script names the event each block answers:

```
begin GameMode
    ...
end
```

`blocks.BLOCK_MAP` turns that name into a Papyrus event, and `assemble.events`
**drops any block whose type is absent from that table, body and all** — the
table is the vocabulary of what survives conversion at all.

TES3 has no such vocabulary. A script opens with its OWN name:

```
Begin TR_m4_NPC_AndoCTThug01
    ...
End
```

so the script name lands in the block type, never matches `BLOCK_MAP`, and the
whole body is discarded. Measured over TR_Mainland.esm before the fix:

| | |
|---|---|
| Blocks parsed | 3,569 |
| Blocks matching `BLOCK_MAP` | **0** |
| Scripts with an executable body | **0 of 3,569** |

Oblivion.esm and Nehrim.esm sit at 0.4% and 0.5% empty over the same pass, so
this was TES3-only. The parser was never at fault: it parsed all 3,569 without
error and built correct statement trees. Only the routing failed, which is why
the output was a well-formed shell — the properties survive because variable
declarations are hoisted in `parse()` before blocks are assembled.

**A TES3 body runs every frame while its object is loaded**, which is exactly
what `gamemode` means, so the implicit block routes to that type and reaches
`Event OnUpdate()` through the existing map. No new event kind is introduced.

### Recognizing the implicit block

`begin` takes the name two ways, and both mean the same thing:

| Source | Parsed as | Why |
|---|---|---|
| `Begin ScriptName` | `btype='scriptname'` | a bare `IDENT` |
| `Begin "ScriptName"` | `btype=''`, name in `filter` | `_parse_block` takes the type only from an `IDENT`, and a quoted name lexes as a `STRING` |

Both are matched against the script's own EditorID rather than a fixed list,
since the name is arbitrary. Measured over TR_Mainland's 3,569 `Begin` lines:
3,534 name the EditorID exactly and the remaining 35 are the quoted or
CS-truncated spelling of it — **none** names a TES4 block type, so matching on
the script's own name cannot collide with a real one.
