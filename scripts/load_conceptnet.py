#!/usr/bin/env python3
"""
Load ConceptNet 5.7 assertions into symbol_hub.conceptnet_edges.

Streams the 497 MB gz dump, keeping only /c/en/ -> /c/en/ edges where either
lemma is in our working vocabulary (Bliss label words + label phrases + top
30k common words). Adds sense_a/sense_b columns (e.g. "n/wn/object") so the
WordNet-sense evidence survives for WSD.

Licence: ConceptNet 5.7 is CC BY-SA 4.0 — this table must stay server-side
and separable; it is never exported into the shipped resolver asset.

    uv run python scripts/load_conceptnet.py
"""
import gzip
import json
import os
import sqlite3

import urllib.request

DUMP = os.path.join("data", "raw", "conceptnet-assertions-5.7.0.csv.gz")
DUMP_URL = "https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz"
DB = os.path.join("data", "processed", "symbol_hub.db")
VOCAB = os.path.join("data", "processed", "vocab.txt")
KEEP_RELS = None  # keep all relations; filter at query time


def working_vocab() -> set:
    vocab = set()
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT DISTINCT l.norm FROM labels l JOIN symbols s ON s.id = l.symbol_id "
        "WHERE s.dataset = 'bliss-bciav' AND l.lang IN ('en','eng')"
    ).fetchall()
    for (norm,) in rows:
        if norm:
            vocab.add(norm)
            for w in norm.split():
                vocab.add(w)
    conn.close()
    # top common words for query coverage
    if os.path.exists(VOCAB):
        with open(VOCAB, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 30000:
                    break
                vocab.add(line.strip())
    return vocab


def parse_concept(uri: str):
    """/c/en/bank/n/wn/object -> (bank, n/wn/object) ; None for non-en."""
    parts = uri.split("/")
    if len(parts) < 4 or parts[1] != "c" or parts[2] != "en":
        return None
    lemma = parts[3].replace("_", " ").lower()
    sense = "/".join(parts[4:]) if len(parts) > 4 else ""
    return lemma, sense


def main() -> None:
    if not os.path.exists(DUMP):
        os.makedirs(os.path.dirname(DUMP), exist_ok=True)
        print(f"downloading {DUMP_URL} (~475 MB)…")
        urllib.request.urlretrieve(DUMP_URL, DUMP)

    vocab = working_vocab()
    print(f"working vocabulary: {len(vocab)} lemmas")

    conn = sqlite3.connect(DB)
    conn.execute("ALTER TABLE conceptnet_edges ADD COLUMN sense_a TEXT DEFAULT ''")
    conn.execute("ALTER TABLE conceptnet_edges ADD COLUMN sense_b TEXT DEFAULT ''")
    conn.execute("DELETE FROM conceptnet_edges")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cn_lemma ON conceptnet_edges(lemma)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cn_other ON conceptnet_edges(other)")

    n_seen = n_kept = 0
    batch = []
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in f:
            n_seen += 1
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            rel = parts[1].rsplit("/", 1)[-1]
            a = parse_concept(parts[2])
            b = parse_concept(parts[3])
            if not a or not b:
                continue
            (lemma_a, sense_a), (lemma_b, sense_b) = a, b
            if lemma_a not in vocab and lemma_b not in vocab:
                continue
            try:
                weight = float(json.loads(parts[4]).get("weight", 1.0))
            except json.JSONDecodeError:
                weight = 1.0
            batch.append((lemma_a, rel, lemma_b, weight, "conceptnet-5.7", sense_a, sense_b))
            n_kept += 1
            if len(batch) >= 20000:
                conn.executemany(
                    "INSERT INTO conceptnet_edges (lemma, relation, other, weight, source, sense_a, sense_b) "
                    "VALUES (?,?,?,?,?,?,?)", batch)
                batch = []
            if n_seen % 5_000_000 == 0:
                conn.commit()
                print(f"  {n_seen/1e6:.0f}M lines seen, {n_kept/1e6:.2f}M kept…")
    if batch:
        conn.executemany(
            "INSERT INTO conceptnet_edges (lemma, relation, other, weight, source, sense_a, sense_b) "
            "VALUES (?,?,?,?,?,?,?)", batch)
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM conceptnet_edges").fetchone()[0]
    dist = conn.execute(
        "SELECT relation, COUNT(*) FROM conceptnet_edges GROUP BY relation ORDER BY 2 DESC LIMIT 12").fetchall()
    conn.close()
    print(f"done: {n_seen/1e6:.0f}M assertions seen -> {total} edges stored "
          f"({n_kept and total==n_kept and 'ok' or 'MISMATCH'})")
    for rel, n in dist:
        print(f"  {rel:<28} {n}")


if __name__ == "__main__":
    main()
