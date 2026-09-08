"""FO3/FNV command handlers whose behaviour depends on the RECEIVER's record.

A row in `FALLOUT_COMMAND_ROWS` renders one template for every call site. A
handler belongs here only where FO3/FNV spell one command against two different
receiver types, which a single template cannot express.

Exported as a plain table rather than through `commands.command`, so this module
imports nothing from `commands` and the two cannot form a cycle.

See: docs/commentary/script_convert.md#getfactionrelation-has-two-receivers
"""


def faction_relation(ctx, call):
    """`<x>.GetFactionRelation <actor>` -- reaction toward another actor.

    Declines (returns None) for an ACTOR receiver so the row renders the real
    `Actor.GetFactionReaction`; only the FACTION receiver is handled here,
    because Papyrus has no faction-toward-actor read at all.
    """
    ref = call.ref or ''
    fid = ctx.xref.edid_to_formid.get(ref.lower(), '') if ctx.xref else ''
    if not fid or ctx.xref.record_type.get(fid, '') != 'FACT':
        return None
    return ctx.note(f'NE: {ref}.GetFactionRelation - Papyrus has no '
                    f'faction-toward-actor reaction (read as 0)')


#: TES4 command name -> handler, merged into `commands.REGISTRY`.
FALLOUT_HANDLERS = {'getfactionrelation': faction_relation}
