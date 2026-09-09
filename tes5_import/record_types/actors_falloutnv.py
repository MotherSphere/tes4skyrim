"""FO3/FNV actor templates: resolving TPLT so a spawn stub knows what it is.

FO3/FNV actors inherit by category. A spawn stub owns nothing but a TPLT and
the ACBS Template Flags naming the categories it takes from that template, so
its model, name, AI data and stats all live one or more links away. Nothing
here writes TPLT into the output, so an unflattened category is lost outright.

Also holds the AIDT combat tiers, which FO3/FNV stores in the same enums TES5
uses and Oblivion stores as 0-100 scalars.

See: docs/commentary/tes5_import_falloutnv_actors.md
"""

from ..text_reader import get_formid, get_int, get_str

#: Template Flags bits (wbDefinitionsCommon.pas:7715).
_USE_AI_DATA = 1 << 4
_USE_MODEL = 1 << 6
_USE_BASE_DATA = 1 << 7

#: A template chain longer than this is a cycle; FNV's deepest is 3.
_MAX_DEPTH = 8

#: Inherited with Model/Animation, and read by the creature race builder.
_MODEL_KEYS = ('Model.MODL', 'Model.MODB', 'Model.MODT')

#: Inherited with AI Data; Aggression and Confidence drive the combat tiers.
_AIDT_KEYS = ('AIDT.Aggression', 'AIDT.Confidence', 'AIDT.EnergyLevel',
              'AIDT.Responsibility', 'AIDT.Mood', 'AIDT.Services',
              'AIDT.Teaches', 'AIDT.MaxTraining', 'AIDT.Assistance',
              'AIDT.AggroRadiusBehavior', 'AIDT.AggroRadius')

#: Each inherited category: its Template Flags bit and the keys it carries.
_CATEGORIES = ((_USE_MODEL, _MODEL_KEYS),
               (_USE_AI_DATA, _AIDT_KEYS),
               (_USE_BASE_DATA, ('FULL',)))


#: Highest legal TES5 tier: wbAggressionEnum is 0-3, wbConfidenceEnum 0-4.
_MAX_AGGRESSION, _MAX_CONFIDENCE = 3, 4


def aidt_tiers(rec: dict) -> tuple:
    """FO3/FNV (Aggression, Confidence) as TES5 tiers, clamped to their enums.

    See: docs/commentary/tes5_import_falloutnv_actors.md#aggression-is-already-a-tier
    """
    return (min(get_int(rec, 'AIDT.Aggression'), _MAX_AGGRESSION),
            min(get_int(rec, 'AIDT.Confidence'), _MAX_CONFIDENCE))


#: Types a TPLT chain can pass through. FO3/FNV has LVLN as well as LVLC.
_TEMPLATE_SIGS = ('CREA', 'NPC_', 'LVLC', 'LVLN')


def _index_actors(by_type: dict, master_export: dict) -> dict:
    """FormID -> record for every actor and leveled actor list in scope."""
    index = {}
    sources = [master_export.values()] if master_export else []
    sources.extend(by_type.get(sig, []) for sig in _TEMPLATE_SIGS)
    for group in sources:
        for rec in group:
            if get_str(rec, 'Signature') in _TEMPLATE_SIGS:
                index[get_formid(rec, 'FormID')] = rec
    return index


def _chain(rec: dict, index: dict):
    """Every actor down this record's template chain, nearest first.

    A leveled-list link resolves through its entries, which is how FNV points
    a stub at an actor: stub -> LVLC/LVLN -> CREA/NPC_. ``rec`` is not yielded.
    """
    seen = set()
    queue = [(rec, 0)]
    while queue:
        node, depth = queue.pop(0)
        fid = get_formid(node, 'FormID')
        if depth > _MAX_DEPTH or fid in seen:
            continue
        seen.add(fid)
        if node is not rec:
            yield node
        nxt = [get_formid(node, 'TPLT.Template')]
        nxt += [get_formid(node, f'Entry[{i}].FormID')
                for i in range(get_int(node, 'EntryCount', 0))]
        queue += [(index[f], depth + 1) for f in nxt if f and f in index]


def _first_owning(rec: dict, index: dict, key: str) -> dict:
    """The nearest actor down the chain that owns ``key``, or None."""
    for node in _chain(rec, index):
        if get_str(node, key):
            return node
    return None


def _flatten_one(rec: dict, index: dict) -> bool:
    """Copy every category ``rec``'s flags claim down from its template.

    A category is skipped when the stub already owns its lead key, so a stub
    that overrides one of them keeps its own.
    """
    flags = get_int(rec, 'ACBS.TemplateFlags')
    filled = False
    for bit, keys in _CATEGORIES:
        if not flags & bit or get_str(rec, keys[0]):
            continue
        donor = _first_owning(rec, index, keys[0])
        if donor is None:
            continue
        for key in keys:
            if get_str(donor, key):
                rec[key] = donor[key]
        if bit == _USE_MODEL:
            _copy_nifz(rec, donor)
        filled = True
    return filled


def _copy_nifz(rec: dict, donor: dict) -> None:
    """Carry the donor's NIFZ model list across; the body-set lookup keys off it."""
    count = get_int(donor, 'NIFZCount', 0)
    if not count:
        return
    rec['NIFZCount'] = str(count)
    for i in range(count):
        rec[f'NIFZ[{i}]'] = donor[f'NIFZ[{i}]']


def flatten_actor_templates(by_type: dict, master_export: dict = None) -> int:
    """Copy each FO3/FNV stub's inherited categories down from its template.

    Mutates the record dicts in ``by_type``, so it must run before the creature
    race builder and any actor conversion. Returns the number flattened.
    """
    index = _index_actors(by_type, master_export)
    flattened = 0
    for sig in ('CREA', 'NPC_'):
        for rec in by_type.get(sig, []):
            flattened += _flatten_one(rec, index)
    return flattened
