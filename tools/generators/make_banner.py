"""Regenerate the GUI banner: TES / AUTO-CONVERT in the Oblivion font.

Usage:
    python tools/generators/make_banner.py [--svg <path>] [--png <path>]

Defaults to docs/assets/banner.{svg,png} -- the pair the GUI loads at runtime.

Both title tiers are traced from `references/oblivion-font.ttf` into real SVG
outlines rather than a `font-family` reference, so the banner renders
identically on a machine that has never seen the font. Both carry the brass
ramp measured from the vanilla Dwemer puzzle cube that
`tools/generators/make_app_icon.py` applies to the lexicon cube, so the banner
and the app icon read as one set; the divider, not a color change, is what
separates the two tiers.

The PNG is rendered FROM the SVG, so the two can never drift.
"""
import argparse
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from tools.generators import dwemer_palette

ROOT = Path(__file__).resolve().parent.parent.parent
FONT = ROOT / "references" / "oblivion-font.ttf"

TITLE = "TES"
SUBTITLE = "AUTO-CONVERT"
TAGLINE = "GAMEBRYO \u2192 SKYRIM CONVERSION"

W = 960

#: Ink band within the 220-unit layout space, measured from the rendered alpha.
INK_TOP, INK_BOTTOM = 28.5, 188.0

BRASS = dwemer_palette.BANNER_TITLE_STOPS


def glyph_paths(text, size, letter_spacing=0.0):
    """Trace `text` to (path_d, x_offset, advance) at `size` px em."""
    font = TTFont(FONT)
    cmap = font.getBestCmap()
    glyphs = font.getGlyphSet()
    upem = font["head"].unitsPerEm
    scale = size / upem

    out, x = [], 0.0
    for ch in text:
        gname = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        glyphs[gname].draw(pen)
        d = pen.getCommands()
        adv = glyphs[gname].width * scale
        if d:
            out.append((d, x, scale))
        x += adv + letter_spacing
    return out, x


def gradient_stops(gid, stops):
    body = "".join(
        f'\n      <stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return (f'    <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'{body}\n    </linearGradient>')


def _tier(text, size, spacing, baseline, fill):
    """One centered title tier as (edge_svg, face_svg).

    Each glyph is emitted twice: a dark offset copy that reads as the carved
    edge, then the lit face over it.
    """
    paths, width = glyph_paths(text, size, letter_spacing=spacing)
    tx = (W - width) / 2

    edge, face = [], []
    for d, x, scale in paths:
        t = (f'translate({tx + x:.2f} {baseline}) '
             f'scale({scale:.5f} {-scale:.5f})')
        edge.append(f'<path transform="{t}" d="{d}"/>')
        face.append(f'<path transform="{t}" d="{d}"/>')
    return ("".join(edge),
            f'<g fill="{fill}">{"".join(face)}</g>')


def build_svg():
    """The banner SVG: two brass title tiers, a divider, then the tagline.

    Authored in the full 220-unit space the shipped banner used, so its sizes
    and baselines carry over unchanged; the viewBox is then cropped to the ink
    band, because the banner is transparent and an empty margin would become
    dead padding around the GUI sidebar logo.
    """
    top_edge, top_face = _tier(TITLE, 88, 10, 92, "url(#brass)")
    low_edge, low_face = _tier(SUBTITLE, 43, 6, 156, "url(#brass)")

    crop_h = INK_BOTTOM - INK_TOP

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {INK_TOP} {W} {crop_h}" width="{W}" height="{crop_h:g}" role="img" aria-label="{TITLE} {SUBTITLE}">
  <defs>
{gradient_stops("brass", BRASS)}
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#a86f24" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#d9a441" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#a86f24" stop-opacity="0"/>
    </linearGradient>
    <filter id="engrave" x="-8%" y="-25%" width="116%" height="150%">
      <feDropShadow dx="0" dy="2" stdDeviation="1.6" flood-color="#000000" flood-opacity="0.65"/>
    </filter>
  </defs>

  <!-- No background rect: the banner is transparent so it sits on whatever
       panel color the GUI theme is using, instead of punching a dark hole. -->

  <!-- Both tiers: Oblivion font traced to outlines, one Dwemer brass ramp -->
  <g filter="url(#engrave)">
    <g fill="#2a1a08" opacity="0.85" transform="translate(0 2)">
      {top_edge}{low_edge}
    </g>
    {top_face}
    {low_face}
  </g>

  <!-- Divider rule, between the two title tiers -->
  <rect x="230" y="108" width="500" height="2" fill="url(#rule)"/>

  <text x="{W // 2}" y="188" text-anchor="middle" font-family="Georgia, serif"
        font-size="15" letter-spacing="6" fill="#8f9aa6">{TAGLINE}</text>
</svg>
'''


def render_png(svg_path: Path, png_path: Path, scale: int = 2) -> bool:
    """Rasterise the SVG so the PNG can never drift from its source.

    Headless Edge/Chrome rather than cairosvg: the machine has no libcairo, and
    a browser is the same engine that renders the SVG everywhere else, so the
    PNG matches what the vector actually looks like.
    """
    import base64
    import shutil
    import subprocess
    import tempfile

    browsers = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    exe = next((b for b in browsers if Path(b).exists()), None)
    if exe is None:
        return False

    out_w = W * scale
    out_h = round((INK_BOTTOM - INK_TOP) * scale)

    # Wrap the SVG in a page sized to the exact output so the screenshot needs
    # no cropping: a bare --screenshot of an .svg letterboxes it in a viewport.
    svg_b64 = base64.b64encode(svg_path.read_bytes()).decode("ascii")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "html,body{margin:0;padding:0;background:transparent}"
        f"img{{display:block;width:{out_w}px;height:{out_h}px}}"
        "</style></head><body>"
        f"<img src='data:image/svg+xml;base64,{svg_b64}'></body></html>"
    )

    tmp = Path(tempfile.mkdtemp(prefix="banner_"))
    try:
        page = tmp / "page.html"
        page.write_text(html, encoding="utf-8")
        shot = tmp / "shot.png"
        subprocess.run(
            [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
             f"--screenshot={shot}",
             f"--window-size={out_w},{out_h}",
             "--default-background-color=00000000",
             page.as_uri()],
            check=True, capture_output=True, timeout=90)
        if not shot.exists():
            return False
        shutil.copyfile(shot, png_path)
        return True
    except (subprocess.SubprocessError, OSError):
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--svg",
                    default=str(ROOT / "docs" / "assets" / "banner.svg"))
    ap.add_argument("--png",
                    default=str(ROOT / "docs" / "assets" / "banner.png"))
    a = ap.parse_args()

    svg = build_svg()
    Path(a.svg).write_text(svg, encoding="utf-8")
    print(f"wrote {a.svg} ({len(svg)} bytes)")

    if render_png(Path(a.svg), Path(a.png)):
        print(f"wrote {a.png} (rendered from the SVG at 2x)")
    else:
        print("no SVG renderer found - SVG written, PNG NOT regenerated")


if __name__ == "__main__":
    main()
