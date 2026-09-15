"""FO3/FNV command handlers whose behaviour depends on the RECEIVER's record.

A row in `FALLOUT_COMMAND_ROWS` renders one template for every call site. A
handler belongs here only where FO3/FNV spell one command against two different
receiver types, which a single template cannot express.

Exported as a plain table rather than through `commands.command`, so this module
imports nothing from `commands` and the two cannot form a cycle.

See: docs/commentary/script_convert.md#getfactionrelation-has-two-receivers
"""

from script_convert.constants import safe_property_name, typed_already


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


#: FO3/FNV command -> Quest native it becomes, the quest argument as receiver.
_QUEST_NATIVES = {
    'setobjectivedisplayed': 'SetObjectiveDisplayed',
    'setobjectivecompleted': 'SetObjectiveCompleted',
    'setobjectivefailed': 'SetObjectiveFailed',
    'getobjectivedisplayed': 'IsObjectiveDisplayed',
    'getobjectivecompleted': 'IsObjectiveCompleted',
    'getobjectivefailed': 'IsObjectiveFailed',
    'setquestdelay': 'RegisterForSingleUpdate',
}


def quest_native(ctx, call):
    """`<cmd> <quest> <args...>` -- Papyrus makes the quest the receiver.

    The quest property keeps a type it already has (a TES4_<script> class
    answers these natives and its variable reads need that type).
    See: docs/commentary/script_convert.md#fnv-objective-commands
    """
    parts = ctx.arg_srcs()
    if len(parts) < 2:
        return None
    prop = safe_property_name(parts[0].strip())
    if not typed_already(ctx.sc.property_refs, prop):
        ctx.sc.property_refs[prop] = 'Quest'
    args = ', '.join(call.arg(i) for i in range(1, len(parts)))
    return f'{prop}.{_QUEST_NATIVES[call.name]}({args})'


#: TES4 command name -> handler, merged into `commands.REGISTRY`.
FALLOUT_HANDLERS = {'getfactionrelation': faction_relation,
                    **{name: quest_native for name in _QUEST_NATIVES}}
