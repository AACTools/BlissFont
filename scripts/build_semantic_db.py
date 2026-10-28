#!/usr/bin/env python3
"""
bliss_semantic.db — a queryable semantic database of all BCI-AV symbols.

One SQLite file unifying everything the project knows about each symbol:

  symbols      bci_id, glosses (5 langs), category, proposed_unicode,
               pua_stable (0xF0000+bci_id), blissary_id, bliss_svg_builder_code
  relations    derivation edges parent_bci -> component_bci (compositional graph)
  word_index   inverted index: English gloss word -> bci_id, with head flag
  symbol_vecs  50-d GloVe mean vector per symbol (for nearest-symbol queries)
  symbols_fts  FTS5 full-text index over English glosses

Planned (schema reserved, tables empty until data is licensed/imported):

  conceptnet_edges  ConceptNet 5.7 edges keyed by English lemma (CC BY-SA 4.0,
                    share-alike: keep this table separable/optional — load from
                    the 475MB assertions dump, NOT the rate-limited public API)
  gs_concepts       GlobalSymbols concept links (their Bliss set is CC BY-SA;
                    concepts are ConceptNet-keyed, ~77-85% accurate per their
                    own ICCHP 2020 evaluation — treat as an index, not truth)

Commands:
    uv run python scripts/build_semantic_db.py build
    uv run python scripts/build_semantic_db.py search  bank
    uv run python scripts/build_semantic_db.py similar 12626          # financial bank
    uv run python scripts/build_semantic_db.py compose fire water     # -> steam-ish symbols
    uv run python scripts/build_semantic_db.py stats
"""
import json
import math
import os
import sqlite3
import struct
import sys

DB_PATH = os.path.join("data", "processed", "bliss_semantic.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
VOCAB_PATH = os.path.join("data", "processed", "vocab.txt")
VECTORS_PATH = os.path.join("data", "processed", "vectors.bin")
DIM = 50

STOP = {
    "to", "the", "a", "an", "of", "and", "or", "in", "on", "at", "for", "with",
    "used", "use", "form", "mark", "marker", "symbol", "multiple", "any",
    "person", "thing",
}


def load_glove() -> tuple[dict[str, int], memoryview]:
    vocab = {}
    with open(VOCAB_PATH, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            vocab[line.strip()] = i
    with open(VECTORS_PATH, "rb") as f:
        raw = memoryview(f.read())
    return vocab, raw


def vec_at(vocab, raw, word):
    i = vocab.get(word)
    if i is None:
        return None
    off = i * DIM * 2  # float16
    vals = struct.unpack(f"<{DIM}e", raw[off:off + DIM * 2])
    return vals


def mean_vector(vocab, raw, words) -> tuple:
    acc = [0.0] * DIM
    n = 0
    for w in words:
        v = vec_at(vocab, raw, w)
        if v:
            for d in range(DIM):
                acc[d] += v[d]
            n += 1
    if n:
        acc = [x / n for x in acc]
    return tuple(acc), n


def cos(a, b) -> float:
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return num / (na * nb)


def gloss_words(gloss) -> list[str]:
    if not gloss:
        return []
    out, seen = [], set()
    for part in str(gloss).lower().replace("(", " ").replace(")", " ").split(","):
        for w in part.replace("-", " ").replace("_", " ").split():
            w = "".join(ch for ch in w if ch.isalpha())
            if len(w) > 1 and w not in STOP and w not in seen:
                seen.add(w)
                out.append(w)
    return out


def build() -> None:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)
    vocab, raw = load_glove()

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE symbols (
            bci_id TEXT PRIMARY KEY,
            gloss_en TEXT, gloss_sv TEXT, gloss_de TEXT, gloss_nl TEXT, gloss_fr TEXT,
            category TEXT,
            proposed_unicode TEXT,
            pua_stable TEXT,
            blissary_id INTEGER,
            bliss_svg_builder_code TEXT,
            is_indicator INTEGER DEFAULT 0
        );
        CREATE TABLE relations (
            parent_bci TEXT,
            component_bci TEXT,
            component_gloss TEXT
        );
        CREATE TABLE word_index (
            word TEXT,
            bci_id TEXT,
            is_head INTEGER DEFAULT 0
        );
        CREATE INDEX idx_word ON word_index(word);
        CREATE INDEX idx_rel_parent ON relations(parent_bci);
        CREATE INDEX idx_rel_comp ON relations(component_bci);
        CREATE VIRTUAL TABLE symbols_fts USING fts5(
            bci_id UNINDEXED, gloss_en
        );
        CREATE TABLE symbol_vecs (
            bci_id TEXT PRIMARY KEY,
            dim INTEGER,
            vec BLOB,           -- float32 little-endian
            coverage INTEGER    -- how many gloss words hit GloVe
        );
        -- reserved for future, licence-separable extensions (see module docstring)
        CREATE TABLE conceptnet_edges (
            lemma TEXT, relation TEXT, other TEXT, weight REAL,
            source TEXT DEFAULT 'conceptnet-5.7'
        );
        CREATE TABLE gs_concepts (
            bci_id TEXT, concept_uri TEXT, label TEXT
        );
        """
    )

    for r in records:
        g = r.get("glosses") or {}
        bci = r["bci_id"]
        en = g.get("en", "")
        is_indicator = 1 if r.get("category") == "Indicator" else 0
        pua_stable = (
            f"U+{0xF0000 + int(bci):X}" if str(bci).isdigit() else None
        )
        cur.execute(
            "INSERT INTO symbols VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                bci, en, g.get("sv"), g.get("de"), g.get("nl"), g.get("fr"),
                r.get("category"), r.get("proposed_unicode"), pua_stable,
                r.get("blissary_id"), r.get("bliss_svg_builder_code"),
                is_indicator,
            ),
        )
        if en:
            cur.execute("INSERT INTO symbols_fts VALUES (?,?)", (bci, en))
        words = gloss_words(en)
        for w in words:
            cur.execute(
                "INSERT INTO word_index VALUES (?,?,?)", (w, bci, 1 if words and w == words[0] else 0)
            )
        for comp in r.get("derivation_components") or []:
            cur.execute(
                "INSERT INTO relations VALUES (?,?,?)",
                (bci, comp.get("bci_id"), comp.get("gloss")),
            )
        vec, coverage = mean_vector(vocab, raw, words[:6])
        if coverage:
            cur.execute(
                "INSERT INTO symbol_vecs VALUES (?,?,?,?)",
                (bci, DIM, struct.pack(f"<{DIM}f", *vec), coverage),
            )

    conn.commit()
    n_sym = cur.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    n_rel = cur.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    n_vec = cur.execute("SELECT COUNT(*) FROM symbol_vecs").fetchone()[0]
    n_ind = cur.execute("SELECT COUNT(*) FROM symbols WHERE is_indicator=1").fetchone()[0]
    conn.close()
    print(
        f"bliss_semantic.db built: {n_sym} symbols, {n_rel} derivation edges, "
        f"{n_vec} vectors, {n_ind} indicators -> {DB_PATH}"
    )


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def search(word: str) -> None:
    conn = _connect()
    rows = conn.execute(
        "SELECT s.bci_id, s.gloss_en, s.category, s.pua_stable, s.proposed_unicode "
        "FROM word_index w JOIN symbols s ON s.bci_id = w.bci_id "
        "WHERE w.word = ? ORDER BY w.is_head DESC, s.gloss_en LIMIT 15",
        (word.lower(),),
    ).fetchall()
    for r in rows:
        print(f"{r['bci_id']:>6}  {r['gloss_en'][:48]:<48} {r['category'] or '':<12} {r['pua_stable']} {r['proposed_unicode'] or ''}")
    if not rows:
        print("(no matches)")


def similar(bci_id: str, k: int = 12) -> None:
    conn = _connect()
    row = conn.execute(
        "SELECT s.bci_id, s.gloss_en, v.vec FROM symbol_vecs v "
        "JOIN symbols s ON s.bci_id = v.bci_id WHERE s.bci_id = ?",
        (bci_id,),
    ).fetchone()
    if not row:
        print("no vector for that id")
        return
    target = struct.unpack(f"<{DIM}f", row["vec"])
    best = []
    for other in conn.execute("SELECT bci_id, vec FROM symbol_vecs"):
        if other["bci_id"] == bci_id:
            continue
        v = struct.unpack(f"<{DIM}f", other["vec"])
        best.append((cos(target, v), other["bci_id"]))
    best.sort(reverse=True)
    glosses = {
        r[0]: r[1]
        for r in conn.execute(
            f"SELECT bci_id, gloss_en FROM symbols WHERE bci_id IN "
            f"({','.join('?' * len(best[:k]))})",
            [b for _, b in best[:k]],
        )
    }
    print(f"nearest to {bci_id} ({row['gloss_en']}):")
    for score, b in best[:k]:
        print(f"  {score:.3f}  {b:>6}  {glosses.get(b, '')[:50]}")


def compose(words: list[str], k: int = 12) -> None:
    vocab, raw = load_glove()
    target, coverage = mean_vector(vocab, raw, [w.lower() for w in words])
    if not coverage:
        print("none of those words are in the GloVe vocab")
        return
    conn = _connect()
    best = []
    for row in conn.execute("SELECT bci_id, vec FROM symbol_vecs"):
        v = struct.unpack(f"<{DIM}f", row["vec"])
        best.append((cos(target, v), row["bci_id"]))
    best.sort(reverse=True)
    glosses = {
        r[0]: r[1]
        for r in conn.execute(
            f"SELECT bci_id, gloss_en FROM symbols WHERE bci_id IN "
            f"({','.join('?' * len(best[:k]))})",
            [b for _, b in best[:k]],
        )
    }
    print(f"symbols nearest to {' + '.join(words)}:")
    for score, b in best[:k]:
        print(f"  {score:.3f}  {b:>6}  {glosses.get(b, '')[:50]}")


def stats() -> None:
    conn = _connect()
    for q, label in [
        ("SELECT COUNT(*) FROM symbols", "symbols"),
        ("SELECT COUNT(*) FROM relations", "derivation edges"),
        ("SELECT COUNT(*) FROM symbol_vecs", "embedded symbols"),
        ("SELECT COUNT(*) FROM word_index", "word-index rows"),
        ("SELECT COUNT(DISTINCT word) FROM word_index", "distinct English words"),
        ("SELECT COUNT(*) FROM symbols WHERE proposed_unicode IS NOT NULL", "official proposed scalars"),
        ("SELECT COUNT(*) FROM symbols WHERE blissary_id IS NOT NULL", "crosswalked to Blissary"),
        ("SELECT COUNT(*) FROM conceptnet_edges", "conceptnet edges (placeholder)"),
    ]:
        print(f"{label:<34} {conn.execute(q).fetchone()[0]}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "build":
        build()
    elif cmd == "search" and len(sys.argv) > 2:
        search(sys.argv[2])
    elif cmd == "similar" and len(sys.argv) > 2:
        similar(sys.argv[2])
    elif cmd == "compose" and len(sys.argv) > 3:
        compose(sys.argv[2:])
    elif cmd == "stats":
        stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
