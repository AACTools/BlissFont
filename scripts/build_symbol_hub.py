#!/usr/bin/env python3
"""
symbol_hub.db — a multilingual, multi-set semantic hub for AAC symbol libraries.

Answers: "can the Bliss semantic DB design extend to other symbol libraries
(ARASAAC, Mulberry, …)?" — yes: same spine (symbols + labels + relations +
vectors), plus a datasets registry and a cross-set link layer.

Sourcing policy (deliberate):
  - Blissymbolics: **BCI-AV 2025-02-15 is the source of truth** (19 languages,
    derivation explanations, WinBliss sequences — richer than any mirror).
    GlobalSymbols is NOT used for Bliss except as an optional cross-check.
  - Other sets (ARASAAC, Mulberry, …): loaded from GlobalSymbols' v1 API
    (https://globalsymbols.com/api/v1/pictos?symbolset=<slug>) which returns
    POS, image URLs, and multilingual labels per symbol. Swap in the v2 API
    (keyed) or direct per-set APIs later without schema changes.

Schema:
  datasets        slug, name, publisher, license, source_url, fetched_at
  symbols         dataset slug, key (BCI id / GS picto id), pos, gloss_en,
                  extra JSON (pua_stable, proposed_unicode, blissary_id,
                  winbliss, image_url, ...)
  labels          symbol ref, lang (BCI: ISO-639-1; GS: ISO-639-3), text
  derivations     Bliss compositional graph (parent -> component refs)
  links           cross-set symbol pairs with method + score
                  (v1 methods: label-exact-en, label-head-en — honest caveat:
                  label matching is the weak layer; ConceptNet/Numberbatch
                  similarity is the planned upgrade, table reserved below)
  conceptnet_edges  reserved (load from the 5.7.0 dump locally; CC BY-SA 4.0 —
                    keep separable; never hit the public API at runtime)

Licensing: each dataset keeps its own license in `datasets.license`; ARASAAC
is CC BY-NC-SA — do not redistribute the combined hub file, and keep per-set
exports separable.

Usage:
    uv run python scripts/build_symbol_hub.py build                  # Bliss only
    uv run python scripts/build_symbol_hub.py load-gs arasaac --limit 1500
    uv run python scripts/build_symbol_hub.py link
    uv run python scripts/build_symbol_hub.py stats
    uv run python scripts/build_symbol_hub.py search doctor
    uv run python scripts/build_symbol_hub.py linked 13656            # dentist
"""
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

DB_PATH = os.path.join("data", "processed", "symbol_hub.db")
BLISS_JSON = os.path.join("data", "processed", "bliss_character_data.json")
GS_API = "https://globalsymbols.com/api/v1"
UA = "Mozilla/5.0 (X11; Linux x86_64) AACTools-BlissFont/0.1 (research; contact via github.com/AACTools)"


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

BLISS_DATASET = (
    "bliss-bciav",
    "Blissymbolics (BCI-AV 2025-02-15)",
    "Blissymbolics Communication International",
    "BCI-AV release terms (see NOTICE.md / T-106)",
    "http://www.blissymbolics.net/BCI-AV_2025-02-15/",
)


def norm(s: str) -> str:
    return " ".join(
        "".join(ch for ch in str(s or "").lower() if ch.isalnum() or ch.isspace()).split()
    )


def label_variants(text: str) -> list[str]:
    """Gloss cells are often comma/semicolon/pipe-separated alternatives
    ('bank_card,money_card') — split so cross-set label matching works."""
    out = []
    for part in str(text or "").replace("_", " ").replace("-", " ").split(","):
        part = part.strip()
        if part and part not in out:
            out.append(part)
    return out


def head_word(s: str) -> str:
    return norm(s).split(" ")[0] if norm(s) else ""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            slug TEXT PRIMARY KEY, name TEXT, publisher TEXT,
            license TEXT, source_url TEXT, fetched_at TEXT, symbol_count INTEGER
        );
        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY,
            dataset TEXT REFERENCES datasets(slug),
            key TEXT, pos TEXT, gloss_en TEXT, extra TEXT,
            UNIQUE(dataset, key)
        );
        CREATE TABLE IF NOT EXISTS labels (
            symbol_id INTEGER REFERENCES symbols(id),
            lang TEXT, text TEXT, norm TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_labels_norm ON labels(norm);
        CREATE TABLE IF NOT EXISTS derivations (
            parent_symbol_id INTEGER REFERENCES symbols(id),
            component_symbol_id INTEGER REFERENCES symbols(id),
            component_gloss TEXT
        );
        CREATE TABLE IF NOT EXISTS links (
            a_symbol_id INTEGER REFERENCES symbols(id),
            b_symbol_id INTEGER REFERENCES symbols(id),
            method TEXT, score REAL,
            UNIQUE(a_symbol_id, b_symbol_id, method)
        );
        CREATE TABLE IF NOT EXISTS conceptnet_edges (
            lemma TEXT, relation TEXT, other TEXT, weight REAL,
            source TEXT DEFAULT 'conceptnet-5.7'
        );
        """
    )
    conn.commit()


# ------------------------------------------------------------------ bliss loader
def load_bliss(conn: sqlite3.Connection) -> None:
    with open(BLISS_JSON, "r", encoding="utf-8") as f:
        records = json.load(f)

    slug, name, publisher, license_, source = BLISS_DATASET
    conn.execute(
        "INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?)",
        (slug, name, publisher, license_, source, time.strftime("%Y-%m-%d"), len(records)),
    )

    cur = conn.cursor()
    n_sym = n_lab = n_der = 0
    id_by_bci = {}
    for r in records:
        bci = r["bci_id"]
        g = r.get("glosses") or {}
        extra = {
            "pua_stable": f"U+{0xF0000 + int(bci):X}" if str(bci).isdigit() else None,
            "proposed_unicode": r.get("proposed_unicode"),
            "blissary_id": r.get("blissary_id"),
            "bliss_svg_builder_code": r.get("bliss_svg_builder_code"),
            "winbliss": r.get("winbliss"),
            "category": r.get("category"),
        }
        cur.execute(
            "INSERT OR REPLACE INTO symbols (dataset, key, pos, gloss_en, extra) VALUES (?,?,?,?,?)",
            (slug, bci, r.get("category"), g.get("en", ""), json.dumps(extra, ensure_ascii=False)),
        )
        sid = cur.lastrowid
        id_by_bci[bci] = sid
        n_sym += 1
        for lang, text in g.items():
            if text:
                for var in label_variants(text):
                    cur.execute(
                        "INSERT INTO labels (symbol_id, lang, text, norm) VALUES (?,?,?,?)",
                        (sid, lang, var, norm(var)),
                    )
                    n_lab += 1
    for r in records:
        for comp in r.get("derivation_components") or []:
            cid = id_by_bci.get(str(comp.get("bci_id")))
            if cid and id_by_bci.get(r["bci_id"]):
                cur.execute(
                    "INSERT INTO derivations VALUES (?,?,?)",
                    (id_by_bci[r["bci_id"]], cid, comp.get("gloss")),
                )
                n_der += 1
    conn.commit()
    print(f"Bliss: {n_sym} symbols, {n_lab} labels, {n_der} derivation edges")


# ------------------------------------------------------------- GlobalSymbols loader
def load_gs(conn: sqlite3.Connection, slug: str, limit: int) -> None:
    cur = conn.cursor()
    # dataset metadata
    try:
        sets = json.loads(http_get(f"{GS_API}/symbolsets", timeout=30))
        meta = next((s for s in sets if s.get("slug") == slug), None)
    except Exception as e:  # noqa: BLE001
        print(f"warning: could not fetch symbolset metadata ({e})")
        meta = None
    lic = (meta or {}).get("licence", {})
    cur.execute(
        "INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?)",
        (
            slug,
            (meta or {}).get("name", slug),
            (meta or {}).get("publisher", "GlobalSymbols"),
            f"{lic.get('name', 'see source')} {lic.get('url', '')}".strip(),
            f"{GS_API}/pictos?symbolset={slug}",
            time.strftime("%Y-%m-%d"),
            None,
        ),
    )
    conn.commit()

    page, n_sym, n_lab = 1, 0, 0
    per_page = 100
    while True:
        url = f"{GS_API}/pictos?symbolset={urllib.parse.quote(slug)}&page={page}&per_page={per_page}"
        payload = json.loads(http_get(url, timeout=60))
        items = payload.get("items") or payload.get("data") or []
        if not items:
            break
        for it in items:
            labels = it.get("labels") or []
            en = next((l["text"] for l in labels if l.get("language") == "eng"), "")
            extra = {
                "gs_id": it.get("id"),
                "image_url": it.get("image_url"),
                "native_format": it.get("native_format"),
                "description": next(
                    (l.get("description") for l in labels if l.get("language") == "eng"), None
                ),
            }
            cur.execute(
                "INSERT OR REPLACE INTO symbols (dataset, key, pos, gloss_en, extra) VALUES (?,?,?,?,?)",
                (slug, str(it.get("id")), it.get("part_of_speech"), en, json.dumps(extra, ensure_ascii=False)),
            )
            sid = cur.lastrowid
            n_sym += 1
            for l in labels:
                for var in label_variants(l.get("text")):
                    cur.execute(
                        "INSERT INTO labels (symbol_id, lang, text, norm) VALUES (?,?,?,?)",
                        (sid, l.get("language"), var, norm(var)),
                    )
                    n_lab += 1
        conn.commit()
        print(f"  page {page}: {len(items)} symbols (total {n_sym})")
        if limit and n_sym >= limit:
            break
        if len(items) < per_page:
            break
        page += 1
        time.sleep(0.2)  # be polite to the unauthenticated v1 API

    cur.execute("UPDATE datasets SET symbol_count=? WHERE slug=?", (n_sym, slug))
    conn.commit()
    print(f"GlobalSymbols[{slug}]: {n_sym} symbols, {n_lab} labels")


# ----------------------------------------------------------------- cross-set links
def link(conn: sqlite3.Connection) -> None:
    """v1 linking: exact-English-label match, then head-word match, Bliss <-> each other set."""
    cur = conn.cursor()
    sets = [r["slug"] for r in cur.execute("SELECT slug FROM datasets WHERE slug != 'bliss-bciav'")]
    if not sets:
        print("no external datasets loaded — run `load-gs <slug>` first")
        return

    # Bliss English labels -> symbol ids
    bliss = {}
    for row in cur.execute(
        "SELECT l.norm, s.id, l.text FROM labels l JOIN symbols s ON s.id = l.symbol_id "
        "WHERE s.dataset = 'bliss-bciav' AND l.lang = 'en'"
    ):
        bliss.setdefault(row["norm"], row["id"])

    bliss_heads = {}
    for row in cur.execute(
        "SELECT l.text, s.id FROM labels l JOIN symbols s ON s.id = l.symbol_id "
        "WHERE s.dataset = 'bliss-bciav' AND l.lang = 'en'"
    ):
        bliss_heads.setdefault(head_word(row["text"]), row["id"])

    for slug in sets:
        n_exact = n_head = 0
        # fetchall() first: interleaving INSERTs into an open SELECT cursor on
        # the same connection silently truncates the iteration.
        ext_rows = cur.execute(
            "SELECT l.norm, l.text, s.id FROM labels l JOIN symbols s ON s.id = l.symbol_id "
            "WHERE s.dataset = ? AND l.lang = 'eng'",
            (slug,),
        ).fetchall()
        for row in ext_rows:
            if row["norm"] in bliss:
                cur.execute(
                    "INSERT OR IGNORE INTO links VALUES (?,?,?,?)",
                    (bliss[row["norm"]], row["id"], "label-exact-en", 1.0),
                )
                n_exact += 1
            else:
                hw = head_word(row["text"])
                if hw and hw in bliss_heads:
                    cur.execute(
                        "INSERT OR IGNORE INTO links VALUES (?,?,?,?)",
                        (bliss_heads[hw], row["id"], "label-head-en", 0.6),
                    )
                    n_head += 1
        conn.commit()
        ext = cur.execute("SELECT symbol_count FROM datasets WHERE slug=?", (slug,)).fetchone()[0]
        print(f"{slug}: exact links {n_exact}, head-word links {n_head} (of {ext} symbols)")


# ------------------------------------------------------------------------- queries
def search(word: str) -> None:
    conn = connect()
    q = norm(word)
    rows = conn.execute(
        "SELECT s.dataset, s.key, s.pos, s.gloss_en, s.extra, l.lang, l.text "
        "FROM labels l JOIN symbols s ON s.id = l.symbol_id "
        "WHERE l.norm LIKE ? ORDER BY s.dataset, CASE WHEN l.norm = ? THEN 0 ELSE 1 END, s.gloss_en "
        "LIMIT 40",
        (f"%{q}%", q),
    ).fetchall()
    for r in rows:
        print(f"{r['dataset']:<14} {r['key']:>7}  {str(r['gloss_en'])[:40]:<40} {r['lang']}:{r['text'][:24]}")
    if not rows:
        print("(no matches)")


def linked(key: str) -> None:
    conn = connect()
    base = conn.execute(
        "SELECT s.id, s.dataset, s.key, s.gloss_en FROM symbols s WHERE s.dataset='bliss-bciav' AND s.key=?",
        (key,),
    ).fetchone()
    if not base:
        print("no such Bliss id")
        return
    print(f"{base['key']} {base['gloss_en']} links to:")
    for r in conn.execute(
        "SELECT b.dataset, b.key, b.gloss_en, k.method, k.score FROM links k "
        "JOIN symbols b ON b.id = CASE WHEN k.a_symbol_id = ? THEN k.b_symbol_id ELSE k.a_symbol_id END "
        "WHERE k.a_symbol_id = ? OR k.b_symbol_id = ? ORDER BY k.score DESC, b.dataset LIMIT 25",
        (base["id"], base["id"], base["id"]),
    ):
        print(f"  [{r['method']:<15} {r['score']}] {r['dataset']:<14} {r['key']:>7}  {str(r['gloss_en'])[:40]}")


def stats() -> None:
    conn = connect()
    for d in conn.execute("SELECT * FROM datasets ORDER BY slug"):
        n_lab = conn.execute("SELECT COUNT(*) FROM labels l JOIN symbols s ON s.id=l.symbol_id WHERE s.dataset=?", (d["slug"],)).fetchone()[0]
        langs = conn.execute("SELECT COUNT(DISTINCT l.lang) FROM labels l JOIN symbols s ON s.id=l.symbol_id WHERE s.dataset=?", (d["slug"],)).fetchone()[0]
        print(f"{d['slug']:<16} {d['symbol_count'] or 0:>6} symbols  {n_lab:>6} labels  {langs:>3} langs  {d['license'][:40]}")
    for m in conn.execute("SELECT method, COUNT(*) FROM links GROUP BY method"):
        print(f"links[{m['method']}] = {m[1]}")
    n = conn.execute("SELECT COUNT(*) FROM derivations").fetchone()[0]
    print(f"derivation edges = {n}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "build":
        conn = connect()
        schema(conn)
        load_bliss(conn)
        conn.close()
    elif cmd == "load-gs" and len(sys.argv) > 2:
        slug = sys.argv[2]
        limit = 0
        if "--limit" in sys.argv:
            limit = int(sys.argv[sys.argv.index("--limit") + 1])
        conn = connect()
        schema(conn)
        load_gs(conn, slug, limit)
        conn.close()
    elif cmd == "link":
        conn = connect()
        link(conn)
        conn.close()
    elif cmd == "search" and len(sys.argv) > 2:
        search(sys.argv[2])
    elif cmd == "linked" and len(sys.argv) > 2:
        linked(sys.argv[2])
    elif cmd == "stats":
        stats()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
