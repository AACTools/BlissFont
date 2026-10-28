#!/usr/bin/env python3
"""
Full build: raw BCI-AV + Blissary data -> fonts, unicode files, databases,
web asset. Runs the pipeline in dependency order so a fresh clone reproduces
everything the site and repos ship.

    uv run python scripts/build_all.py            # everything
    uv run python scripts/build_all.py --skip-download
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STEPS = [
    # (script, needs data/raw?)
    ("download_data.py", False),        # fetch BCI-AV zips/xlsx/PDFs
    ("build_database.py", True),        # -> bliss_character_data.json + SQLite
    ("analyze_derivations.py", True),   # + derivation_components, collation
    ("map_unicode.py", True),           # + proposed scalars, Unibliss.txt
    ("map_annotations.py", True),       # + N1866/MSBI/radical annotations
    ("build_font.py", True),            # BlissFont (outline) x3 weights
    ("build_blissary_font.py", True),   # BlissaryFont (stroke) x3 weights
    ("integrate_crosswalk.py", True),   # + Blissary B-codes
    ("merge_all_languages.py", True),   # + 18 languages, WinBliss
    ("build_rime_dict.py", True),       # RIME dict/schema/custom yamls
    ("build_vector_db.py", True),       # web GloVe db (50d, 100k)
    ("build_semantic_db.py", True),     # bliss_semantic.db
    ("build_symbol_hub.py build", True),  # hub DB (bliss loader only)
    ("export_web_asset.py", True),      # data/web/bliss_resolver.bin
]


def main() -> None:
    skip_download = "--skip-download" in sys.argv
    for script, needs_raw in STEPS:
        if skip_download and script == "download_data.py":
            print(f"== skip {script} ==")
            continue
        if needs_raw and not os.path.isdir(os.path.join("data", "raw")):
            raise SystemExit("data/raw missing — run without --skip-download first.")
        print(f"\n== {script} ==")
        subprocess.run([sys.executable, os.path.join(HERE, *script.split())], check=True)
    print("\nAll steps complete. Serve locally:  python3 -m http.server")


if __name__ == "__main__":
    main()
