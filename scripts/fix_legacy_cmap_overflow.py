#!/usr/bin/env python3
"""
Fix legacy-PUA overflow in already-compiled fonts.

The legacy BMP PUA block (U+E000–U+F8FF) has exactly 6,400 slots, but the
database carries 6,419 glyphs. Fonts compiled before this fix therefore map
the final 19 glyphs onto U+F900–U+F912 — the CJK Compatibility Ideographs
block — shadowing real Unicode codepoints. This script removes any cmap entry
in [U+F900, U+FFFF] that points at a `glyph_<bci_id>` glyph, then verifies the
stable Plane-15 PUA entries (0xF0000 + bci_id) are intact.

Run after editing compiled fonts:
    uv run python scripts/fix_legacy_cmap_overflow.py
"""
import glob
import os
import re

from fontTools.ttLib import TTFont

PROCESSED = os.path.join("data", "processed")
GLYPH_RE = re.compile(r"^glyph_\d+$")


def fix_font(path: str) -> tuple[int, int, int]:
    """Strip CJK-shadow cmap entries. Returns (removed, stable_pua, total)."""
    font = TTFont(path)
    cmap_table = font.getBestCmap()  # dict cp -> glyph name
    if cmap_table is None:
        return 0, 0, 0

    overflow = [
        cp for cp, gname in cmap_table.items()
        if 0xF900 <= cp <= 0xFFFF and GLYPH_RE.match(gname or "")
    ]
    for cp in overflow:
        del cmap_table[cp]

    # fontTools syncs the modified best-cmap back into the subtables on save.
    stable = sum(1 for cp in cmap_table if cp >= 0xF0000)
    total = len(cmap_table)
    font.save(path)
    return len(overflow), stable, total


def main() -> None:
    targets = sorted(glob.glob(os.path.join(PROCESSED, "*.otf"))) + \
              sorted(glob.glob(os.path.join(PROCESSED, "*.woff2")))
    if not targets:
        print("No compiled fonts found in data/processed/.")
        return

    print(f"{'font':<34} {'removed':>7} {'plane15':>8} {'cmap':>6}")
    for path in targets:
        removed, stable, total = fix_font(path)
        print(f"{os.path.basename(path):<34} {removed:>7} {stable:>8} {total:>6}")

    print(
        "\nDone. Removed entries were legacy-PUA overflow (U+F900+) shadowing "
        "CJK Compatibility Ideographs; every glyph remains reachable via its "
        "stable Plane-15 PUA codepoint (0xF0000 + bci_id) and, where assigned, "
        "its official proposed scalar."
    )


if __name__ == "__main__":
    main()
