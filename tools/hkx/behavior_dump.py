"""Dump the state machines of a Havok behavior packfile XML, names resolved.

Reads the hkobject XML that hkxcmd (LE) and tools/hkx/hkxconv (SSE) both
emit, and prints every hkbStateMachine with its states, each state's
generator chain (clip triggers included), its transitions (event NAMES,
target state, condition expression, flags) and the behavior files it
references. This is the reading tool for patching a vanilla humanoid
graph; the writing side is asset_convert/havok/gun_graph_falloutnv.py.

    python tools/hkx/behavior_dump.py <graph.xml> [--name SUBSTR] [--vars]
        [--events SUBSTR] [--refs]

--name filters state machines by name substring; --vars lists the variable
table; --events lists event names matching a substring; --refs lists the
hkbBehaviorReferenceGenerator targets.
"""

import argparse
import sys
import xml.etree.ElementTree as ET


def parse(path: str) -> dict:
    """{ref: (class, {param name: element})} for every top-level object."""
    root = ET.parse(path).getroot()
    out = {}
    for section in root.iter('hksection'):
        for obj in section.findall('hkobject'):
            params = {p.get('name'): p for p in obj.findall('hkparam')}
            out[obj.get('name')] = (obj.get('class'), params)
    return out


def text(params: dict, name: str) -> str:
    """A scalar param's text ('' when absent)."""
    el = params.get(name)
    return (el.text or '').strip() if el is not None else ''


def string_table(objs: dict) -> tuple:
    """(event names, variable names) from the graph string data."""
    for cls, p in objs.values():
        if cls == 'hkbBehaviorGraphStringData':
            ev = [s.text or '' for s in p['eventNames'].findall('hkcstring')]
            va = [s.text or '' for s in p['variableNames'].findall('hkcstring')]
            return ev, va
    return [], []


def _sub(el, name: str) -> str:
    """Text of the named hkparam directly under `el`."""
    for p in el.findall('hkparam'):
        if p.get('name') == name:
            return (p.text or '').strip()
    return ''


def _transitions(objs, ref, events):
    """Readable lines for one hkbStateMachineTransitionInfoArray."""
    if ref not in objs:
        return []
    lines = []
    for t in objs[ref][1]['transitions'].findall('hkobject'):
        eid = int(_sub(t, 'eventId') or -1)
        cond = _sub(t, 'condition')
        expr = text(objs[cond][1], 'expression') if cond in objs else ''
        name = events[eid] if 0 <= eid < len(events) else str(eid)
        lines.append(f'      on {name} -> state {_sub(t, "toStateId")}'
                     f'{" if " + expr if expr else ""}  [{_sub(t, "flags")}]')
    return lines


def _triggers(objs, ref, events):
    """'event@time' for every trigger of an hkbClipTriggerArray."""
    if ref not in objs:
        return ''
    out = []
    for t in objs[ref][1]['triggers'].findall('hkobject'):
        eid = -1
        for p in t.findall('hkparam'):
            if p.get('name') == 'event':
                eid = int(_sub(p.find('hkobject'), 'id') or -1)
        name = events[eid] if 0 <= eid < len(events) else str(eid)
        rel = '-' if _sub(t, 'relativeToEndOfClip') == 'true' else ''
        out.append(f'{name}@{rel}{_sub(t, "localTime")}')
    return ' triggers[' + ', '.join(out) + ']' if out else ''


def bindings(objs, p, variables) -> str:
    """' bind{member<-variable,...}' for an object's variableBindingSet."""
    ref = text(p, 'variableBindingSet')
    if ref not in objs:
        return ''
    out = []
    for b in objs[ref][1]['bindings'].findall('hkobject'):
        vi = int(_sub(b, 'variableIndex') or -1)
        name = variables[vi] if 0 <= vi < len(variables) else str(vi)
        out.append(f'{_sub(b, "memberPath")}<-{name}')
    return ' bind{' + ','.join(out) + '}' if out else ''


def _chain(objs, ref, events, depth=0, variables=()):
    """The generator chain below `ref` (modifier generators unwrapped)."""
    if ref not in objs or depth > 6:
        return []
    cls, p = objs[ref]
    line = f'{"  " * depth}{cls} {text(p, "name")}' + bindings(objs, p, variables)
    if cls == 'hkbClipGenerator':
        line += (f'  <- {text(p, "animationName")} {text(p, "mode")}'
                 + _triggers(objs, text(p, 'triggers'), events))
    if cls == 'hkbBehaviorReferenceGenerator':
        line += f'  -> {text(p, "behaviorName")}'
    if cls == 'BSiStateTaggingGenerator':
        line += f'  iState={text(p, "iStateToSetAs")} prio={text(p, "iPriority")}'
    out = [line]
    for key in ('generator', 'pDefaultGenerator', 'pBlenderGenerator'):
        child = text(p, key)
        if child in objs:
            out += _chain(objs, child, events, depth + 1, variables)
    if cls == 'hkbBlenderGenerator':
        for c in p['children'].text.split():
            gen = text(objs[c][1], 'generator') if c in objs else ''
            out += _chain(objs, gen, events, depth + 1, variables)
    if cls == 'hkbManualSelectorGenerator':
        for i, c in enumerate(p['generators'].text.split()):
            out.append(f'{"  " * depth}  [{i}]')
            out += _chain(objs, c, events, depth + 2, variables)
    if cls == 'hkbStateMachine':
        out.append(f'{"  " * depth}  (machine, see its own listing)')
    return out


def dump_machine(objs, ref, events, variables):
    """Print one state machine."""
    cls, p = objs[ref]
    print(f'== {ref} hkbStateMachine {text(p, "name")} '
          f'start={text(p, "startStateId")} sync={text(p, "syncVariableIndex")}'
          + bindings(objs, p, variables))
    for line in _transitions(objs, text(p, 'wildcardTransitions'), events):
        print('   wildcard' + line[6:])
    for sref in p['states'].text.split():
        _scls, sp = objs.get(sref, ('', {}))
        print(f'   state {text(sp, "stateId")} {text(sp, "name")}')
        for line in _chain(objs, text(sp, 'generator'), events, 3, variables):
            print(line)
        for line in _transitions(objs, text(sp, 'transitions'), events):
            print(line)


def main():
    """Parse the arguments, print the requested tables and machines."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('xml')
    ap.add_argument('--name', help='only machines whose name contains this')
    ap.add_argument('--vars', action='store_true')
    ap.add_argument('--events', help='list event names containing this')
    ap.add_argument('--refs', action='store_true')
    args = ap.parse_args()
    objs = parse(args.xml)
    events, variables = string_table(objs)
    if args.vars:
        for i, v in enumerate(variables):
            print(f'var {i} {v}')
    if args.events:
        for i, e in enumerate(events):
            if args.events.lower() in e.lower():
                print(f'event {i} {e}')
    if args.refs:
        for ref, (cls, p) in objs.items():
            if cls == 'hkbBehaviorReferenceGenerator':
                print(f'{ref} {text(p, "name")} -> {text(p, "behaviorName")}')
    for ref, (cls, p) in objs.items():
        if cls != 'hkbStateMachine':
            continue
        if args.name and args.name.lower() not in text(p, 'name').lower():
            continue
        dump_machine(objs, ref, events, variables)
    return 0


if __name__ == '__main__':
    sys.exit(main())
