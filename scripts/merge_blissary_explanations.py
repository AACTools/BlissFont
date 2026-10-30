#!/usr/bin/env python3
"""
Merge per-entry explanations from the Blissary dictionary snapshot
(bundled with the local blissbench clone; CC-BY-SA 4.0, © Blissary/BCI —
see NOTICE) into bliss_character_data.json as `explanation_blissary`.

These prose explanations are richer than the xlsx derivation column and
feed the resolver's detail view and the BlissNLP reviewer sheet ("why was
this flagged").

Usage:
    uv run python scripts/merge_blissary_explanations.py [snapshot.json]
"""
import json
import os
import sys

DEFAULT_SNAPSHOT = os.path.join(
    "..", "blissbench", "data", "blissary-bliss-dictionary-export-2026-05-23.json")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")


def main() -> None:
    snap_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
    if not os.path.exists(snap_path):
        raise SystemExit(f"snapshot not found: {snap_path} (clone blissbench or pass a path)")
    with open(snap_path, "r", encoding="utf-8") as f:
        snapshot = json.load(f)
    entries = snapshot.get("data", snapshot)

    by_bci: dict[str, str] = {}
    for e in entries:
        bci = e.get("bciAvId")
        expl = (e.get("explanation") or "").strip()
        if bci is not None and expl:
            by_bci[str(bci)] = expl

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    added = 0
    for r in records:
        expl = by_bci.get(str(r["bci_id"]))
        if expl and not r.get("explanation_blissary"):
            r["explanation_blissary"] = expl
            added += 1

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"merged {added} explanations of {len(by_bci)} available "
          f"into {len(records)} records")


if __name__ == "__main__":
    main()
