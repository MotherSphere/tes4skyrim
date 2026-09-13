"""The asset namespace must survive every process boundary.

Module state does not cross a spawn, so a pool worker re-imports game_paths at
DEFAULT_NAMESPACE.  Ten pools once wrote `tes4` names under FalloutNV for
exactly that reason, and no amount of grepping for a stray literal could find
it -- there is no wrong string and no wrong helper, only a lost variable.
See: docs/commentary/asset_convert_texture.md#namespace-crosses-process-boundaries
"""
import multiprocessing as mp
import os
import sys

import pytest

from asset_convert.game_paths import (DEFAULT_NAMESPACE, NAMESPACE_ENV,
                                      current_namespace, namespace_for,
                                      owns_namespace, set_namespace)

#: Helpers the once-broken pools reach, as (import path, attribute, call).
PROBES = (
    ('asset_convert.havok.gun_anim_falloutnv', 'anim_prefix', ()),
    ('asset_convert.ui.book_inam', 'inv_mesh_dir', ()),
    ('asset_convert.ui.book_inam', 'inv_tex_dir', ()),
    ('asset_convert.character.hair_pipeline', 'out_rel_dir', ()),
    ('script_convert.constants', 'script_prefix', ()),
    ('asset_convert.speedtree.spt_converter', 'bark_tex_dir', ()),
)


def _probe_child(_):
    """Run in a SPAWNED worker: the namespace, plus every probed helper."""
    import importlib
    sys.path.insert(0, os.getcwd())
    from asset_convert.game_paths import current_namespace
    out = {'namespace': current_namespace()}
    for mod, attr, args in PROBES:
        out[attr] = getattr(importlib.import_module(mod), attr)(*args)
    return out


def _in_spawned_child(namespace: str) -> dict:
    """What a freshly spawned worker sees after the parent sets `namespace`."""
    set_namespace(namespace)
    ctx = mp.get_context('spawn')
    with ctx.Pool(1) as pool:
        return pool.map(_probe_child, [0])[0]


@pytest.fixture(autouse=True)
def _restore_namespace():
    """Namespace is process-global, so no test may leak it into another."""
    before = current_namespace()
    yield
    set_namespace(before)


class TestNamespaceCrossesSpawn:
    def test_env_carries_the_namespace(self):
        """set_namespace exports the variable spawn and subprocess inherit."""
        set_namespace('falloutnv')
        assert os.environ[NAMESPACE_ENV] == 'falloutnv'
        set_namespace('tes4')
        assert os.environ[NAMESPACE_ENV] == 'tes4'

    @pytest.mark.parametrize('namespace', ['falloutnv', 'nehrim'])
    def test_spawned_worker_inherits(self, namespace):
        """An UNSEEDED spawned worker must not fall back to the default."""
        got = _in_spawned_child(namespace)
        assert got['namespace'] == namespace
        for _mod, attr, _a in PROBES:
            assert 'tes4' not in got[attr].lower(), f'{attr} -> {got[attr]}'
            assert namespace in got[attr].lower(), f'{attr} -> {got[attr]}'

    def test_oblivion_still_writes_tes4(self):
        """Oblivion keeps `tes4`, so its existing output stays valid."""
        got = _in_spawned_child('tes4')
        assert got['namespace'] == 'tes4'
        assert got['script_prefix'] == 'TES4_'
        assert got['anim_prefix'] == 'Animations\\TES4Guns\\'


def _plugin(root, name, masters=()):
    """An export dir for `name` whose _HEADER.txt lists `masters`."""
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / '_HEADER.txt').write_text(
        ''.join(f'Master[{i}]={m}\n' for i, m in enumerate(masters)),
        encoding='utf-8')
    return d


class TestNamespaceOwnership:
    """Exactly one plugin per namespace writes that namespace's shared files.

    `default_n.dds` sits at a namespace-relative path, so writing it per plugin
    wrote one file once per plugin sharing the namespace.
    See: docs/commentary/asset_convert_texture.md#per-game-asset-namespace
    """

    def test_the_chain_root_owns_its_namespace(self, tmp_path):
        """A masterless plugin named for its namespace writes the shared files."""
        assert owns_namespace(_plugin(tmp_path, 'Nehrim.esm'))

    def test_oblivion_owns_tes4(self, tmp_path):
        """Oblivion roots `tes4` even though the name is not its stem."""
        assert owns_namespace(_plugin(tmp_path, 'Oblivion.esm'))

    def test_a_dependent_does_not(self, tmp_path):
        """A plugin BORROWING the namespace must not write into it."""
        _plugin(tmp_path, 'Oblivion.esm')
        assert not owns_namespace(
            _plugin(tmp_path, 'Knights.esp', ['Oblivion.esm']))

    def test_a_companion_root_does_not(self, tmp_path):
        """A COMPANION_ROOTS plugin is masterless but only JOINS tes4."""
        d = _plugin(tmp_path, 'Morrowind-Morroblivion-Compatibility.esp')
        assert namespace_for(d) == DEFAULT_NAMESPACE
        assert not owns_namespace(d)
