"""FO3/FNV MUSC: a music TRACK where TES5 has a music TYPE.

FO3/FNV `MUSC` names one file (`FNAM`) and a dB gain (`ANAM`); TES5 `MUSC` is
a type holding `MUST` tracks. So each source record becomes a pair, built by
the shared music builders rather than a second music system.

See: docs/commentary/tes4_export_falloutnv.md#music-types
"""

from ..base.text_reader import get_formid, get_str
from .music import build_MUSC, build_MUST

#: A FNV MUSC with no FNAM names no file: it is the authored silence record.
FNV_SILENCE_DURATION = 300.0


def convert_MUSC(rec: dict, writer=None) -> bytes:
    """A FO3/FNV MUSC as a TES5 MUSC, minting the MUST it wraps.

    It takes the one-shot `special` spec, since a named FNV cue must not
    cycle, and its own authored EditorID scopes both records. A record naming
    no file is the engine's silence entry and becomes a Silent Track.

    `ANAM` is a gain, not a duration: TES5's single-track shape carries
    neither, so it is dropped rather than written into FLTV.
    """
    edid = get_str(rec, 'EditorID')
    if not edid or writer is None:
        return b''
    filename = get_str(rec, 'FNAM.FileName')
    source_rel = filename.replace(chr(92), '/') if filename else edid
    track = {'source_rel': source_rel,
             'game_path': filename,
             'stem': source_rel.rsplit('/', 1)[-1].rsplit('.', 1)[0]
                     if filename else 'silence',
             'duration': FNV_SILENCE_DURATION,
             'category': 'special'}
    must_fid = writer.derive_formid('MUST', edid)
    writer.add_record('MUST', build_MUST(track, must_fid, ''))
    return build_MUSC('special', [must_fid], get_formid(rec, 'FormID'),
                      '', edid='MUSTrk%s' % edid)
