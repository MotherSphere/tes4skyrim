"""Package TESRuntime.dll as its own distributable SKSE mod.

The DLL is not a plugin asset: one copy serves every converted mod, so it
ships alone rather than beside any plugin's meshes. Each converted mod
contributes only its own data — the animation cache fragment under
SKSE/Plugins/TESRuntime/animation — which this DLL reads at load.

The archive mirrors what `convert.py --pack-zip-only` produces — output/
Finished Mods/<name>.zip, contents rooted as a Data folder — so a user
installs it exactly like any converted plugin.

Usage:
  python tools/release/package_runtime_dll.py   # -> output/Finished Mods/TESRuntime.zip
  python tools/release/package_runtime_dll.py --output-dir PATH
"""

import argparse
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from output_layout import finished_dir

MOD_NAME = "TESRuntime"

#: Built by tes_runtime/build.bat; the one file this mod exists to deliver.
DLL_PATH = SCRIPT_DIR / "tes_runtime" / "TESRuntime.dll"

#: Where the DLL sits inside the archive's Data root.
ARCNAME = Path("SKSE") / "Plugins" / "TESRuntime.dll"


def package(out_root: Path) -> int:
    """Zip the built DLL into <out_root>/Finished Mods/TESRuntime.zip."""
    if not DLL_PATH.is_file():
        print(f"ERROR: {DLL_PATH} not found — build it first with "
              f"tes_runtime\\build.bat.")
        return 1

    zip_path = finished_dir(out_root) / f"{MOD_NAME}.zip"

    print("=" * 54)
    print("  PACKAGE RUNTIME DLL")
    print("=" * 54)
    print(f"  Source: {DLL_PATH}")
    print(f"  Output: {zip_path}")
    print()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(DLL_PATH, arcname=str(ARCNAME))
        print(f"  + {ARCNAME}")

    size = zip_path.stat().st_size
    print()
    print(f"Packaged -> {zip_path} ({size:,} bytes)")
    print("Install it like any other converted mod: the archive root is the "
          "Data folder. It needs SKSE and the Address Library.")
    return 0


def main() -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Package TESRuntime.dll as a standalone SKSE mod.")
    ap.add_argument("--output-dir", metavar="PATH",
                    help="Output directory (default: output/ in project root)")
    args = ap.parse_args()
    out_root = (Path(args.output_dir) if args.output_dir
                else SCRIPT_DIR / "output")
    return package(out_root)


if __name__ == "__main__":
    sys.exit(main())
