"""Build the web font licensed from Envato Elements into frontend/public/fonts/.

The font is licensed to the owner's Envato account and must not enter this public
repository, so public/fonts/ is gitignored. Without it the app falls back to Geologica.
Download "Hakimi Sans - 22 Styles & Variable" by Zelowtypestudio while signed in to
Envato Elements, then run:

    python frontend/scripts/licensed_fonts.py <hakimi-sans.zip>

Needs fontTools and brotli.
"""

import io
import sys
import zipfile
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

OUT = Path(__file__).resolve().parent.parent / "public" / "fonts"

# Latin, Latin-1, Latin Extended-A (Turkish), punctuation, currency (₺), arrows,
# the minus sign and the ▲▼ markers the app prints beside changes.
UNICODES = "U+0020-007E,U+00A0-017F,U+2000-206F,U+20A0-20CF,U+2190-21FF,U+2212,U+25B2-25BC"


def member(zip_path: str, suffix: str) -> TTFont:
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith(suffix) and "__MACOSX" not in n)
        return TTFont(io.BytesIO(z.read(name)))


def write(font: TTFont, name: str) -> None:
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    options.name_IDs = ["*"]
    options.notdef_outline = True
    sub = subset.Subsetter(options)
    sub.populate(unicodes=subset.parse_unicodes(UNICODES))
    sub.subset(font)
    OUT.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.save(OUT / name)
    print(f"{name}: {(OUT / name).stat().st_size // 1024} KB")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    write(member(sys.argv[1], "ZT Hakimi Variable-VF.ttf"), "hakimi.woff2")


if __name__ == "__main__":
    main()
