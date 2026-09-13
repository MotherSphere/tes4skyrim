"""Staged BSA paths must survive Windows' 260-character MAX_PATH.

Each archive is staged as a hardlink tree under
`output/<plugin>/_bsa_staging_<type>/`, which is LONGER than the source tree it
mirrors.  For a plugin with a long folder name plus creature animdata that
crosses MAX_PATH, and BSArch then fails with a disguised
`EAggregateException` under `-mt`.
See: docs/commentary/asset_convert_bsa.md#staging-past-the-path-limit
"""

import os
import sys

from asset_convert.sources.bsa_pack import long_path, _stage_bin

WIN_ONLY = sys.platform != 'win32'


class TestLongPath:
    """The prefix helper itself."""

    def test_absolute_path_gets_the_prefix(self):
        """An ordinary absolute Windows path is prefixed."""
        if WIN_ONLY:
            return
        got = long_path(r'C:\Users\x\output\plugin\meshes\a.nif')
        assert got == r'\\?\C:\Users\x\output\plugin\meshes\a.nif'

    def test_prefix_is_not_applied_twice(self):
        """A path that already carries the prefix is returned unchanged."""
        already = r'\\?\C:\x\y.nif'
        assert long_path(already) == already

    def test_relative_path_is_untouched(self):
        r"""\\?\ disables path parsing, so a relative path must not get it."""
        assert long_path('meshes/a.nif') == 'meshes/a.nif'

    def test_separators_are_normalized(self):
        r"""\\?\ passes '/' through verbatim, so the path must be normalized."""
        if WIN_ONLY:
            return
        assert '/' not in long_path('C:/Users/x/a.nif')


class TestStagingBeyondMaxPath:
    """The staging tree is built even where the result exceeds MAX_PATH."""

    def test_stage_bin_links_a_path_over_260_chars(self, tmp_path):
        """A staged path longer than MAX_PATH is still linked, with content.

        The relative path is built deep enough that the staged result crosses
        the limit, which is the shape of the real Unique Landscapes failure.
        """
        if WIN_ONLY:
            return
        src = tmp_path / 'src.nif'
        src.write_bytes(b'NIF')

        deep = os.path.join(*(['d' * 40] * 5), 'f' * 40 + '.nif')
        stage = tmp_path / '_bsa_staging_main_0'
        staged = stage / deep
        assert len(str(staged)) > 260, 'test must exercise the limit'

        assert _stage_bin([(src, deep, 3)], stage) == 1
        assert os.path.exists(long_path(staged))
        assert open(long_path(staged), 'rb').read() == b'NIF'
