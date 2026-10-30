#!/usr/bin/env python3
"""
Publish the bidirectional ID map promised to Hannes (2026-10-30):

    BCI-AV id  <->  Blissary B-code  <->  Unicode (official scalar + stable PUA)

Writes data/processed/bliss_bcode_map.json + .csv — one row per symbol that
has a Blissary code (via hlridge/bliss-blissary-bci-id-map, CC-BY-SA).
Offered on the site's downloads tab; the resolver already embeds the codes.

    uv run python scripts/export_bcode_map.py
"""
import csv
import json
import os

JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
OUT_JSON = os.path.join("data", "processed", "bliss_bcode_map.json")
OUT_CSV = os.path.join("data", "processed", "bliss_bcode_map.csv")


def main() -> None:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    rows = []
    for r in records:
        code = r.get("bliss_svg_builder_code")
        if not code:
            continue
        rows.append({
            "bci_av_id": r["bci_id"],
            "blissary_code": code,
            "gloss_en": (r.get("glosses") or {}).get("en", ""),
            "proposed_unicode": r.get("proposed_unicode") or "",
            "pua_stable": (f"U+{0xF0000 + int(r['bci_id']):X}"
                           if str(r["bci_id"]).isdigit() else ""),
        })
    rows.sort(key=lambda x: int(x["bci_av_id"]))

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "license": "BCI-AV CC BY-SA 4.0; crosswalk (c) Blissary/Hannes Ljusas, CC BY-SA 4.0",
            "source": "github.com/hlridge/bliss-blissary-bci-id-map via BlissFont integrate_crosswalk.py",
            "count": len(rows),
            "entries": rows,
        }, f, indent=1, ensure_ascii=False)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} mappings -> {OUT_CSV} / {OUT_JSON}")


if __name__ == "__main__":
    main()
