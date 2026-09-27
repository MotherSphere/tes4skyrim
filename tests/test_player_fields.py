"""Every PlayerCharacter offset the runtimes read goes through PlayerField().

See: docs/commentary/tes_runtime_journal.md#player-fields-move-on-17
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "tes_runtime"
FIELD_RE = re.compile(r"constexpr std::size_t (k(?:Off)?Player\w+) = 0x([0-9a-fA-F]+);")

#: The journal's objective builder, which reads the player's objective count.
BUILDER_ID = 53171


def player_fields() -> dict:
    """{name: 1.6 offset} for every PlayerCharacter offset declared in an ids.h."""
    fields = {}
    for header in RUNTIME.rglob("ids.h"):
        for name, value in FIELD_RE.findall(header.read_text(encoding="utf-8")):
            fields[name] = int(value, 16)
    return fields


def test_player_fields_are_declared():
    """The scan finds the fields the runtimes are known to read."""
    assert {"kOffPlayerObjectives", "kOffPlayerObjectiveCount",
            "kPlayerJailFaction", "kPlayerServeFlags",
            "kOffPlayerJailFaction"} <= set(player_fields())


def test_every_player_field_read_goes_through_player_field():
    """A PlayerCharacter offset used anywhere but inside PlayerField() is a 1.7 crash."""
    names = "|".join(player_fields())
    use = re.compile(rf"(PlayerField\(\s*)?\bids::({names})\b")
    bare = [f"{src.relative_to(ROOT)}:{n}: {m.group(2)}"
            for src in RUNTIME.rglob("*.cpp")
            for n, line in enumerate(src.read_text(encoding="utf-8").splitlines(), 1)
            for m in use.finditer(line) if not m.group(1)]
    assert not bare, "read through PlayerField():\n" + "\n".join(bare)


def objective_count_offset(version: str) -> int:
    """The displacement the builder reads the player's objective count at on `version`."""
    address_lib = pytest.importorskip("tools.disasm.address_lib")
    disasm = pytest.importorskip("tools.disasm.skyrim_disasm")
    exe = address_lib.DEPOT / f"SkyrimSE.{version}.unpacked.exe"
    if not exe.is_file():
        pytest.skip(f"no unpacked {version} exe")
    try:
        rva = address_lib.load(address_lib.find_versionlib(version))[BUILDER_ID]
    except SystemExit:
        pytest.skip(f"no {version} versionlib")
    binary = disasm.Binary(str(exe))
    start, end = binary.func_bounds(rva)
    first = next(i for i in binary.disasm(start, end - start)
                 if i.mnemonic == "mov" and i.op_str.startswith("eax, dword ptr [rcx + 0x5"))
    return first.operands[1].mem.disp


def test_objective_count_moves_by_eight_on_17():
    """1.6.1170 reads the declared offset, 1.7.104 reads it 8 later."""
    declared = player_fields()["kOffPlayerObjectiveCount"]
    assert objective_count_offset("1.6.1170") == declared
    assert objective_count_offset("1.7.104") == declared + 8
