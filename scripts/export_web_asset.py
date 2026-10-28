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
  - SEMANTIC LAYER: per-symbol 50d GloVe mean vectors plus the full 100k-word
    vector vocab (float16, ~11 MB) so out-of-vocabulary queries fall back to
    cosine similarity instead of returning nothing.

What stays out:
  - external label text, image URLs (licences + weight)
  - the full 100k-word vector db (the sandbox ships that separately as vectors.bin)

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
# NOTE: ships as .bin, not .db — the repo .gitignore excludes *.db, and this
# asset MUST be committed so the GitHub Pages demo can fetch it.
OUT = os.environ.get("RESOLVER_OUT", os.path.join(OUT_DIR, "bliss_resolver.bin"))

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
            url TEXT,
            img_url TEXT        -- GlobalSymbols image URL (pointer; art stays on their CDN)
        );
        CREATE INDEX idx_links_bliss ON links(bliss_key);
        -- semantic layer: cosine fallback for OOV queries (float16 blobs)
        CREATE TABLE symbol_vecs (
            symbol_key TEXT PRIMARY KEY, dim INTEGER,
            vec BLOB,          -- float16 little-endian
            coverage INTEGER
        );
        CREATE TABLE word_vecs (
            word TEXT PRIMARY KEY,
            vec BLOB           -- float16 little-endian (full 100k GloVe vocab)
        );
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
        "SELECT sa.key AS bliss_key, sb.dataset AS ds, sb.key AS ek, k.method, k.score, "
        "sb.extra AS ext_extra "
        "FROM links k JOIN symbols sa ON sa.id = k.a_symbol_id "
        "JOIN symbols sb ON sb.id = k.b_symbol_id "
        "WHERE sa.dataset='bliss-bciav'"
    ):
        url = GS_SYMBOL_URL.format(slug=r["ds"], key=r["ek"]) if r["ds"] != "bliss-bciav" else None
        img = None
        if r["ds"] != "bliss-bciav":
            try:
                img = (json.loads(r["ext_extra"] or "{}") or {}).get("image_url")
            except json.JSONDecodeError:
                img = None
        dst.execute("INSERT INTO links VALUES (?,?,?,?,?,?,?)",
                    (r["bliss_key"], r["ds"], r["ek"], r["method"], r["score"], url, img))
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

    # ---- semantic layer --------------------------------------------------
    # 1) per-symbol mean vectors over English gloss words (GloVe 6B.50d)
    # 2) word vectors for the 30k most frequent words + every label word
    vocab_path = os.path.join("data", "processed", "vocab.txt")
    vec_path = os.path.join("data", "processed", "vectors.bin")
    if os.path.exists(vocab_path) and os.path.exists(vec_path):
        import struct

        DIM = 50
        with open(vocab_path, "r", encoding="utf-8") as f:
            vocab = [w.strip() for w in f]
        vindex = {w: i for i, w in enumerate(vocab)}
        with open(vec_path, "rb") as f:
            vraw = f.read()  # float16 little-endian, row-major

        def wvec(word):
            i = vindex.get(word)
            if i is None:
                return None
            off = i * DIM * 2
            return struct.unpack(f"<{DIM}e", vraw[off:off + DIM * 2])

        def pack_f16(values):
            # store half-precision: 100k words x 50d = 10 MB instead of 20 MB
            return struct.pack(f"<{DIM}e", *values)

        STOP = {
            "to", "the", "a", "an", "of", "and", "or", "in", "on", "at", "for",
            "with", "used", "use", "form", "mark", "marker", "symbol",
            "multiple", "any", "person", "thing",
        }

        def gloss_words(gloss):
            out, seen = [], set()
            for part in str(gloss or "").lower().replace("(", " ").replace(")", " ").split(","):
                for w in part.replace("-", " ").replace("_", " ").split():
                    w = "".join(ch for ch in w if ch.isalpha())
                    if len(w) > 1 and w not in STOP and w not in seen:
                        seen.add(w)
                        out.append(w)
            return out

        n_symvec = n_wordvec = 0
        label_words = set()
        for r in src.execute(
            "SELECT key, gloss_en FROM symbols WHERE dataset='bliss-bciav'"
        ):
            words = gloss_words(r["gloss_en"])[:6]
            acc = [0.0] * DIM
            n = 0
            for w in words:
                v = wvec(w)
                if v:
                    for d in range(DIM):
                        acc[d] += v[d]
                    n += 1
            if n:
                for d in range(DIM):
                    acc[d] /= n
                dst.execute(
                    "INSERT INTO symbol_vecs VALUES (?,?,?,?)",
                    (r["key"], DIM, pack_f16(acc), n),
                )
                n_symvec += 1
            label_words.update(words)
        # word vectors: the FULL GloVe vocab (covers rare queries like 'cog'
        # at rank 41k or 'toothache' at 87k), stored as float16
        for w in vocab:
            v = wvec(w)
            if v:
                dst.execute(
                    "INSERT INTO word_vecs VALUES (?,?)",
                    (w, pack_f16(v)),
                )
                n_wordvec += 1
        print(f"semantic layer: {n_symvec} symbol vectors, {n_wordvec} word vectors")

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
