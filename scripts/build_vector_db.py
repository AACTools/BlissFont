#!/usr/bin/env python3
"""
Build the float16 vector database used by the web sandbox and blissbench runner.

Defaults keep the original 50d/100k build (shipped with the web app).
`--dim 300` builds the denser bench-quality database (vectors300.bin +
vocab300.txt, 200k words) used by the blissbench improvement sprint.

    uv run python scripts/build_vector_db.py              # 50d, 100k (web)
    uv run python scripts/build_vector_db.py --dim 300    # 300d, 200k (bench)
"""
import argparse
import json
import os
import urllib.request
import zipfile

import numpy as np

GLOVE_ZIP_URL = "https://huggingface.co/stanfordnlp/glove/resolve/main/glove.6B.zip"
RAW_DIR = os.path.join("data", "raw")
PROCESSED_DIR = os.path.join("data", "processed")
JSON_PATH = os.path.join(PROCESSED_DIR, "bliss_character_data.json")


def ensure_source(dim: int) -> str:
    txt = os.path.join(RAW_DIR, f"glove.6B.{dim}d.txt")
    if os.path.exists(txt):
        return txt
    zpath = os.path.join(RAW_DIR, "glove.6B.zip")
    if not os.path.exists(zpath):
        os.makedirs(RAW_DIR, exist_ok=True)
        print(f"Downloading {GLOVE_ZIP_URL} (~860 MB)...")
        urllib.request.urlretrieve(GLOVE_ZIP_URL, zpath)
    print(f"Extracting glove.6B.{dim}d.txt ...")
    with zipfile.ZipFile(zpath) as z:
        z.extract(f"glove.6B.{dim}d.txt", RAW_DIR)
    return txt


def build(dim: int, max_words: int, suffix: str) -> None:
    txt = ensure_source(dim)
    print(f"Building {suffix or 'default'} vector database from {txt}...")

    bci_words = set()
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
        for rec in records:
            gloss = (rec.get("glosses", {}).get("en") or "").lower().strip()
            gloss_clean = gloss.replace("-(to)", "").replace("_(to)", "").strip()
            for ch in ",;/|":
                for part in gloss_clean.split(ch):
                    for word in part.replace("(", " ").replace(")", " ").replace("_", " ").split():
                        w = word.strip("-")
                        if w:
                            bci_words.add(w)
    print(f"Loaded {len(bci_words)} active BCI-AV vocab terms.")

    vocab, vectors = [], []
    n = 0
    with open(txt, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != dim + 1:
                continue
            word = parts[0].lower()
            if n < max_words or word in bci_words:
                vocab.append(word)
                vectors.append(np.array([float(x) for x in parts[1:]], dtype=np.float32))
            n += 1
            if n % 200000 == 0:
                print(f"  processed {n} source lines...")

    matrix = np.vstack(vectors).astype(np.float16)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    vocab_path = os.path.join(PROCESSED_DIR, f"vocab{suffix}.txt")
    bin_path = os.path.join(PROCESSED_DIR, f"vectors{suffix}.bin")
    with open(vocab_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vocab))
    with open(bin_path, "wb") as f:
        f.write(matrix.tobytes())
    print(f"Wrote {len(vocab)} words, {matrix.nbytes / 1e6:.1f} MB -> {bin_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dim", type=int, default=50)
    ap.add_argument("--words", type=int, default=100000)
    args = ap.parse_args()
    suffix = "" if args.dim == 50 else str(args.dim)
    build(args.dim, args.words, suffix)


if __name__ == "__main__":
    main()
