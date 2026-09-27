"""The saved `outputDir` follows the install it sits in.

See: docs/reference/pipeline.md#the-config-file-is-per-install
"""
import os

from output_layout import DEFAULT_OUTPUT, REPO_ROOT, configured_output, output_setting


def test_default_output_saves_relative():
    """The default output folder is saved as a path inside the install."""
    assert output_setting(str(DEFAULT_OUTPUT)) == "output"
    assert output_setting("") == "output"


def test_relative_setting_reads_against_the_install():
    """A relative saved value resolves inside this install, whatever the cwd."""
    assert configured_output("output") == DEFAULT_OUTPUT
    assert configured_output("") == DEFAULT_OUTPUT
    assert configured_output(None) == DEFAULT_OUTPUT


def test_folder_outside_the_install_saves_in_full(tmp_path):
    """A chosen folder elsewhere keeps its full path, and reads back unchanged."""
    elsewhere = tmp_path / "converted"
    saved = output_setting(str(elsewhere))
    assert os.path.isabs(saved)
    assert configured_output(saved) == elsewhere


def test_subfolder_of_the_install_round_trips():
    """A folder under the install saves relative and reads back to the same place."""
    chosen = REPO_ROOT / "output" / "alt"
    saved = output_setting(str(chosen))
    assert not os.path.isabs(saved)
    assert configured_output(saved) == chosen
