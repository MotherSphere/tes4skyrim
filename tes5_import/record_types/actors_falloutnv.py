"""FO3/FNV actor templates: resolving TPLT so a spawn stub knows what it is.

FO3/FNV actors inherit by category. A spawn stub owns nothing but a TPLT and
the ACBS Template Flags naming the categories it takes from that template, so
its model, race and stats all live one or more links away. TES5 has the same
TPLT mechanism, but every pass in this package reads a CREA's own Model.MODL;
flattening the inherited fields onto the stub therefore fixes all of them at
once, rather than teaching each one to walk the chain.

See: docs/commentary/tes5_import_falloutnv_actors.md
"""

from ..text_reader import get_formid, get_int, get_str

#: Template Flags bit 6 (wbDefinitionsCommon.pas:7715) -- model and animation.
_USE_MODEL = 1 << 6

#: A template chain longer than this is a cycle; FNV's deepest is 3.
_MAX_DEPTH = 8

#: Inherited with Model/Animation, and read by the creature race builder.
_MODEL_KEYS = ('Model.MODL', 'Model.MODB', 'Model.MODT')


def _index_actors(by_type: dict, master_export: dict) -> dict:
    """FormID -> record for every CREA/NPC_ and leveled actor list in scope."""
    index = {}
    sources = [master_export.values()] if master_export else []
    sources.append(by_type.get('CREA', []))
    sources.append(by_type.get('NPC_', []))
    sources.append(by_type.get('LVLC', []))
    for group in sources:
        for rec in group:
            if get_str(rec, 'Signature') in ('CREA', 'NPC_', 'LVLC'):
                index[get_formid(rec, 'FormID')] = rec
    return index


def _first_concrete(rec: dict, index: dict) -> dict:
    """The nearest actor down this record's template chain that owns a model.

    An LVLC link resolves through its entries, which is how FNV points a stub
    at a creature: stub -> LVLC -> CREA. Returns None when the chain runs out
    without reaching an actor that has one.
    """
    seen = set()
    queue = [(rec, 0)]
    while queue:
        node, depth = queue.pop(0)
        fid = get_formid(node, 'FormID')
        if depth > _MAX_DEPTH or fid in seen:
            continue
        seen.add(fid)
        if node is not rec and get_str(node, 'Model.MODL'):
            return node
        nxt = [get_formid(node, 'TPLT.Template')]
        nxt += [get_formid(node, f'Entry[{i}].FormID')
                for i in range(get_int(node, 'EntryCount', 0))]
        queue += [(index[f], depth + 1) for f in nxt if f and f in index]
    return None


def flatten_actor_templates(by_type: dict, master_export: dict = None) -> int:
    """Copy each FO3/FNV stub's inherited model down from its template.

    Mutates the record dicts in ``by_type``, so it must run before the creature
    race builder and any actor conversion. Returns the number flattened.
    """
    index = _index_actors(by_type, master_export)
    flattened = 0
    for sig in ('CREA', 'NPC_'):
        for rec in by_type.get(sig, []):
            if get_str(rec, 'Model.MODL'):
                continue
            if not get_int(rec, 'ACBS.TemplateFlags') & _USE_MODEL:
                continue
            donor = _first_concrete(rec, index)
            if donor is None:
                continue
            for key in _MODEL_KEYS:
                if get_str(donor, key):
                    rec[key] = donor[key]
            count = get_int(donor, 'NIFZCount', 0)
            if count:
                rec['NIFZCount'] = str(count)
                for i in range(count):
                    rec[f'NIFZ[{i}]'] = donor[f'NIFZ[{i}]']
            flattened += 1
    return flattened
