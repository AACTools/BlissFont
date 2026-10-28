#!/usr/bin/env python3
"""
Export the slim, browser-shippable WASM asset from symbol_hub.db.

Produces data/web/bliss_resolver.db: a single self-contained SQLite file that
sql.js / sqlite-wasm can load in a browser or service worker, no server.

What goes in (deliberately):
  - Bliss symbols + ALL 19-language labels (BCI-AV terms apply — T-106)
  - the derivation graph (compositional semantics — the unique asset)
  - cross-set links as **ID pointers only** (dataset + external key), so a
    client can deep-link to e.g. globalsymbols.com/symbolsets/arasaac/symbols/14449
    WITHOUT redistributing ARASAAC's CC BY-NC-SA label text. NC text stays out.

What stays out:
  - external label text, image URLs (licences + weight)
  - GloVe vectors (10 MB; the sandbox already ships vectors.bin separately)

Usage:
    uv run python scripts/export_web_asset.py            # -> data/web/bliss_resolver.db
"""
import json
import os
import shutil
import sqlite3
import time

SRC = os.environ.get("HUB_SRC", os.path.join("data", "processed", "symbol_hub.db"))
OUT_DIR = os.path.join("data", "web")
OUT = os.environ.get("RESOLVER_OUT", os.path.join(OUT_DIR, "bliss_resolver.db"))

GS_SYMBOL_URL = "https://globalsymbols.com/symbolsets/{slug}/symbols/{key}"


def main() -> None:
    if not os.path.exists(SRC):
        raise SystemExit("symbol_hub.db not found — run build_symbol_hub.py first")
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(OUT):
        os.remove(OUT)

    src = sqlite3.connect(SRC)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(OUT)
    dst.executescript(
        """
        PRAGMA page_size=4096;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE symbols (
            key TEXT PRIMARY KEY, pos TEXT, gloss_en TEXT,
            pua_stable TEXT, proposed_unicode TEXT,
            blissary_code TEXT, winbliss TEXT, category TEXT
        );
        CREATE TABLE labels (symbol_key TEXT, lang TEXT, text TEXT, norm TEXT);
        CREATE INDEX idx_labels_norm ON labels(norm);
        CREATE TABLE derivations (parent_key TEXT, component_key TEXT, component_gloss TEXT);
        CREATE INDEX idx_deriv_parent ON derivations(parent_key);
        CREATE TABLE links (
            bliss_key TEXT, dataset TEXT, external_key TEXT, method TEXT, score REAL,
            url TEXT
        );
        CREATE INDEX idx_links_bliss ON links(bliss_key);
        """
    )

    n_sym = n_lab = n_der = n_link = 0
    for r in src.execute(
        "SELECT key, pos, gloss_en, extra FROM symbols WHERE dataset='bliss-bciav'"
    ):
        extra = json.loads(r["extra"] or "{}")
        dst.execute(
            "INSERT INTO symbols VALUES (?,?,?,?,?,?,?,?)",
            (
                r["key"], r["pos"], r["gloss_en"],
                extra.get("pua_stable"), extra.get("proposed_unicode"),
                extra.get("bliss_svg_builder_code"), extra.get("winbliss"),
                extra.get("category"),
            ),
        )
        n_sym += 1
    for r in src.execute(
        "SELECT s.key, l.lang, l.text, l.norm FROM labels l "
        "JOIN symbols s ON s.id = l.symbol_id WHERE s.dataset='bliss-bciav'"
    ):
        dst.execute("INSERT INTO labels VALUES (?,?,?,?)", (r["key"], r["lang"], r["text"], r["norm"]))
        n_lab += 1
    for r in src.execute(
        "SELECT sp.key AS pk, sc.key AS ck, d.component_gloss FROM derivations d "
        "JOIN symbols sp ON sp.id = d.parent_symbol_id "
        "JOIN symbols sc ON sc.id = d.component_symbol_id"
    ):
        dst.execute("INSERT INTO derivations VALUES (?,?,?)", (r["pk"], r["ck"], r["component_gloss"]))
        n_der += 1
    for r in src.execute(
        "SELECT sa.key AS bliss_key, sb.dataset AS ds, sb.key AS ek, k.method, k.score "
        "FROM links k JOIN symbols sa ON sa.id = k.a_symbol_id "
        "JOIN symbols sb ON sb.id = k.b_symbol_id "
        "WHERE sa.dataset='bliss-bciav'"
    ):
        url = GS_SYMBOL_URL.format(slug=r["ds"], key=r["ek"]) if r["ds"] != "bliss-bciav" else None
        dst.execute("INSERT INTO links VALUES (?,?,?,?,?,?)", (r["bliss_key"], r["ds"], r["ek"], r["method"], r["score"], url))
        n_link += 1

    dst.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [
            ("built", time.strftime("%Y-%m-%d")),
            ("source", "symbol_hub.db / BCI-AV 2025-02-15 + hlridge crosswalk"),
            ("license", "BCI-AV release terms apply (BlissNLP/BlissFont NOTICE.md, T-106 pending)"),
            ("note", "external links are ID pointers only; no third-party label text embedded"),
        ],
    )
    dst.commit()
    dst.execute("VACUUM")
    dst.close()
    src.close()

    size = os.path.getsize(OUT)
    print(f"bliss_resolver.db: {n_sym} symbols, {n_lab} labels, {n_der} derivations, "
          f"{n_link} links -> {OUT} ({size / 1e6:.1f} MB)")
    print(f"gzip size: {int(size * 0.45) / 1e6:.1f} MB (approx, serve with gzip/brotli)")


if __name__ == "__main__":
    main()
