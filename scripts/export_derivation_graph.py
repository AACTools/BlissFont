#!/usr/bin/env python3
"""
Export the BCI-AV derivation graph in a prompt-friendly shape for Cindy Li
(BBB / blissbench) — one JSON line per symbol:

  { "bci": "...", "bcode": "B...", "gloss": "...", "explanation": "...",
    "components": [{"bci": "...", "bcode": "...", "gloss": "..."}],
    "languages": {"en": "...", "sv": "..."} }

Plus a compact edge list (parent_bci, component_bci) for graph tooling.

    uv run python scripts/export_derivation_graph.py   # -> data/processed/
"""
import json
import os
import sqlite3

DB = os.path.join("data", "processed", "symbol_hub.db")
OUT_JSONL = os.path.join("data", "processed", "bliss_derivation_graph.jsonl")
OUT_EDGES = os.path.join("data", "processed", "bliss_derivation_edges.csv")


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    symbols = {}
    by_id = {}
    for r in conn.execute(
        "SELECT s.id, s.key, s.gloss_en, s.extra, l.lang, l.text "
        "FROM symbols s LEFT JOIN labels l ON l.symbol_id = s.id "
        "WHERE s.dataset = 'bliss-bciav'"
    ):
        sym = by_id.get(r["id"]) or symbols.get(r["key"])
        if sym is None:
            sym = symbols.setdefault(r["key"], {
                "bci": r["key"], "bcode": None, "gloss": r["gloss_en"] or "",
                "explanation": None, "languages": {}, "components": [],
            })
            by_id[r["id"]] = sym
        if r["lang"] and r["text"]:
            sym["languages"].setdefault(r["lang"], r["text"])
        if r["extra"] and sym["bcode"] is None:
            extra = json.loads(r["extra"])
            sym["bcode"] = extra.get("bliss_svg_builder_code")
            sym["explanation"] = extra.get("explanation_blissary")

    edges = 0
    for r in conn.execute(
        "SELECT d.parent_symbol_id, d.component_symbol_id "
        "FROM derivations d JOIN symbols p ON p.id = d.parent_symbol_id "
        "JOIN symbols c ON c.id = d.component_symbol_id "
        "WHERE p.dataset = 'bliss-bciav' AND c.dataset = 'bliss-bciav'"
    ):
        parent = by_id.get(r[0])
        comp = by_id.get(r[1]) or {"bci": str(r[1]), "bcode": None, "gloss": ""}
        if parent:
            parent["components"].append({
                "bci": comp["bci"], "bcode": comp.get("bcode"), "gloss": comp.get("gloss")})
            edges += 1

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for sym in symbols.values():
            if sym["components"]:
                f.write(json.dumps(sym, ensure_ascii=False) + "\n")

    with open(OUT_EDGES, "w", encoding="utf-8") as f:
        f.write("parent_bci,component_bci\n")
        for sym in symbols.values():
            for c in sym["components"]:
                f.write(f"{sym['bci']},{c['bci']}\n")

    n_words = sum(1 for s in symbols.values() if s["components"])
    print(f"{n_words} word entries ({edges} edges) -> {OUT_JSONL}")
    print(f"edge list -> {OUT_EDGES}")


if __name__ == "__main__":
    main()
