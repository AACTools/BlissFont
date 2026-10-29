# BlissFont

BCI-AV → real fonts. Compiles the [BCI-AV 2025-02-15] release (6,183 symbols,
6,419 glyph records) into OpenType/WOFF2 with GPOS-anchored grammar indicators.

**Live:** https://aactools.github.io/BlissFont/ — sandbox, inspector, symbol hub,
symbolic-web (ruby) demo, downloads.
Pair repo: [BlissNLP](https://github.com/AACTools/BlissNLP) (English→Bliss pipeline).

## Quickstart

```bash
uv sync
uv run python scripts/build_all.py    # fresh clone -> everything
```

Or step-by-step (same order):

```bash
uv run python scripts/download_data.py        # BCI-AV SVGs + xlsx + proposal PDFs
uv run python scripts/build_database.py       # -> bliss_character_data.json + SQLite
uv run python scripts/analyze_derivations.py  # + derivation_components, collation weights
uv run python scripts/map_unicode.py          # + proposed scalars -> Unibliss.txt
uv run python scripts/map_annotations.py      # + N1866 / MSBI / radical annotations
uv run python scripts/build_font.py           # outline fonts x3 weights
uv run python scripts/build_blissary_font.py  # stroke fonts x3 weights
uv run python scripts/integrate_crosswalk.py  # + Blissary B-codes (99.8%)
uv run python scripts/merge_all_languages.py  # + 18 languages, WinBliss
uv run python scripts/build_vector_db.py      # web GloVe db (50d)
uv run python scripts/build_semantic_db.py    # bliss_semantic.db
uv run python scripts/build_symbol_hub.py build
uv run python scripts/export_web_asset.py     # data/web/bliss_resolver.bin
```

## Encoding (3 layers)

| layer | range | use |
|---|---|---|
| official | U+16200–U+167FF (L2/23-138 chart) | ~1,100 proposed scalars — always preferred |
| stable PUA | `0xF0000 + BCI_ID` | every glyph, never shifts — **use this** |
| legacy | U+E000–U+F8FF | capped at 6,400 slots, deprecated |

## Scripts

| script | does |
|---|---|
| `build_font.py` / `build_blissary_font.py` | SVGs → OTF/WOFF2, GPOS anchors from glyph bounds |
| `map_unicode.py` | proposal PDF → `Unibliss.txt` (UCD format) |
| `integrate_crosswalk.py` | joins hlridge B-code crosswalk (99.8%) |
| `merge_all_languages.py` | xlsx → JSON: 18 langs + WinBliss |
| `build_semantic_db.py` | `bliss_semantic.db`: derivations, FTS, vectors |
| `build_symbol_hub.py` | multi-set hub (Bliss + ARASAAC/Mulberry via GlobalSymbols), ConceptNet layer, `link`/`link2`/`wsd` |
| `load_conceptnet.py` | ConceptNet 5.7 → 1.97M edges (server-side only) |
| `export_web_asset.py` | `bliss_resolver.bin` — SQLite-WASM asset for hub.html / ruby.html |
| `fix_legacy_cmap_overflow.py` | strips CJK-shadow entries from built fonts |

## Web pages

- `index.html` — workspace: sandbox, directory, keyboard, inspector, downloads, hub tab, ruby tab
- `hub.html` — concept resolver (search → glyph, 18 langs, derivations, cross-set links, GloVe fallback)
- `ruby.html` — symbolic-web demo: `<ruby lang=zbl>` annotation, display modes, Bliss↔ARASAAC↔Mulberry switching

## Data & licence

See **NOTICE.md** — BCI-AV is **CC BY-SA 4.0** (BCI's citation text included
there); Blissary SVGs © Hannes Ljusås; GloVe © Stanford. Big binaries
(`*.db`, 300d vectors) are gitignored — regenerate with the scripts above.
