#!/usr/bin/env python3
"""
Integrate Hannes Ljusås's Blissary <-> BCI-AV ID crosswalk
(https://github.com/hlridge/bliss-blissary-bci-id-map, CC-BY-SA 4.0) into the
BlissFont database.

Actions:
  1. Download (once) blissary_to_bci_mapping.json into data/raw/crosswalk/.
  2. Attach blissary_id + bliss_svg_builder_code to every matching record in
     data/processed/bliss_character_data.json and to the SQLite symbols table.
  3. Verify coverage both directions and report duplicates / mismatches to
     data/processed/crosswalk_report.json.
  4. If data/raw/blissary/extracted/ exists, check that each mapped BCI id has
     a Blissary SVG file (the source of BlissaryFont).

Usage:
    uv run python scripts/integrate_crosswalk.py
"""
import json
import os
import sqlite3
import urllib.request

CROSSWALK_URL = (
    "https://raw.githubusercontent.com/hlridge/bliss-blissary-bci-id-map/"
    "main/blissary_to_bci_mapping.json"
)
CROSSWALK_DIR = os.path.join("data", "raw", "crosswalk")
CROSSWALK_PATH = os.path.join(CROSSWALK_DIR, "blissary_to_bci_mapping.json")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
REPORT_PATH = os.path.join("data", "processed", "crosswalk_report.json")
BLISSARY_SVG_DIR = os.path.join("data", "raw", "blissary", "extracted")


def download_crosswalk() -> list[dict]:
    os.makedirs(CROSSWALK_DIR, exist_ok=True)
    if not os.path.exists(CROSSWALK_PATH):
        print(f"Downloading crosswalk from {CROSSWALK_URL} ...")
        urllib.request.urlretrieve(CROSSWALK_URL, CROSSWALK_PATH)
    with open(CROSSWALK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept either a bare list or {"entries": [...]}
    if isinstance(data, dict):
        data = data.get("entries", data)
    print(f"Crosswalk entries: {len(data)}")
    return data


def main() -> None:
    entries = download_crosswalk()

    # crosswalk: bciAvId (str) -> list of {blissaryId, blissSvgBuilderCode}
    by_bci: dict[str, list[dict]] = {}
    dup_bci: list[dict] = []
    seen: set[str] = set()
    for e in entries:
        bci = str(e.get("bciAvId", "")).strip()
        if not bci:
            continue
        if bci in seen:
            dup_bci.append(e)
        seen.add(bci)
        by_bci.setdefault(bci, []).append(e)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    our_ids = {r["bci_id"] for r in records}

    matched = 0
    unmatched_ours: list[str] = []
    for r in records:
        hits = by_bci.get(r["bci_id"])
        if hits:
            # First hit wins; duplicates are reported separately.
            r["blissary_id"] = hits[0].get("blissaryId")
            r["bliss_svg_builder_code"] = hits[0].get("blissSvgBuilderCode")
            matched += 1
        else:
            r.pop("blissary_id", None)
            r.pop("bliss_svg_builder_code", None)
            unmatched_ours.append(r["bci_id"])

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    # SQLite mirror
    svg_missing: list[str] = []
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(symbols)")
        cols = {c[1] for c in cur.fetchall()}
        for col in ("blissary_id", "bliss_svg_builder_code"):
            if col not in cols:
                cur.execute(f"ALTER TABLE symbols ADD COLUMN {col} TEXT")
        for r in records:
            if "blissary_id" in r:
                cur.execute(
                    "UPDATE symbols SET blissary_id = ?, bliss_svg_builder_code = ? "
                    "WHERE bci_id = ?",
                    (r.get("blissary_id"), r.get("bliss_svg_builder_code"), r["bci_id"]),
                )
        conn.commit()
        conn.close()
    else:
        print("(SQLite DB not found — JSON only.)")

    # SVG verification (BlissaryFont source), when raw data is present.
    if os.path.isdir(BLISSARY_SVG_DIR):
        for r in records:
            if "blissary_id" in r:
                svg = os.path.join(BLISSARY_SVG_DIR, f"{r['bci_id']}.svg")
                if not os.path.exists(svg):
                    svg_missing.append(r["bci_id"])
        svg_note = f"{len(svg_missing)} mapped ids lack a Blissary SVG"
    else:
        svg_note = "skipped (data/raw/blissary/extracted not present)"

    only_in_crosswalk = sorted(seen - our_ids, key=lambda s: (len(s), s))
    report = {
        "crosswalk_entries": len(entries),
        "crosswalk_unique_bci_ids": len(seen),
        "our_records": len(records),
        "matched": matched,
        "match_rate_ours": round(matched / len(records) * 100, 1),
        "our_unmatched_count": len(unmatched_ours),
        "our_unmatched_sample": unmatched_ours[:50],
        "crosswalk_only_bci_ids": only_in_crosswalk[:200],
        "crosswalk_only_count": len(only_in_crosswalk),
        "duplicate_bci_ids_in_crosswalk": dup_bci[:50],
        "svg_verification": svg_note,
        "svg_missing_sample": svg_missing[:50],
        "source": CROSSWALK_URL,
        "license": "CC-BY-SA 4.0 (c) Blissary / Hannes Ljusas",
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"Matched {matched}/{len(records)} of our records "
          f"({report['match_rate_ours']}%)")
    print(f"Crosswalk BCI ids not in our DB: {len(only_in_crosswalk)}")
    print(f"Crosswalk BCI ids with duplicates: {len(dup_bci)}")
    print(f"SVG verification: {svg_note}")
    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
