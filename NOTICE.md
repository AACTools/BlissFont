# NOTICE — Data sources and attribution

This project builds on top of several open datasets and prior work. If you
redistribute compiled fonts, databases, or derived data, carry these credits
and the respective licence terms with them.

## BCI Authorized Vocabulary of Blissymbolics (BCI-AV) 2025-02-15
- **Author**: Blissymbolics Communication International (BCI),
  https://www.blissymbolics.org — symbol files at
  https://blissymbolics.org/index.php/symbol-files
- **Used for**: the 6,183 active symbols (6,419 glyph records) — English and
  18-language glosses, derivations, POS classes, WinBliss sequences, the
  source SVG vectors of the `BlissFont` outline family, and the label text
  embedded in the shipped `bliss_resolver.bin` asset (share-alike travels
  with it).
- **Licence (verified 2026-10-28 from
  https://www.blissymbolics.org/index.php/licensing):**
  **Creative Commons BY-SA 4.0** (CC BY-SA 4.0). Use and redistribution —
  commercial or otherwise — is permitted with clear BCI attribution;
  derivatives must be redistributed under the same licence. BCI's preferred
  citation, verbatim:
  > The Blissymbolics Communication International Authorized Vocabulary
  > (BCI-AV) is available at www.blissymbolics.org. The BCI-AV and other BCI
  > Blissymbol products are copyright Blissymbolics Communication
  > International (BCI) and made available under the Creative Commons
  > BY-SA 4.0 licence. https://creativecommons.org/licenses/by-sa/4.0/
  >
  > Short form: Parts herein © Blissymbolics Communication International
  > (BCI), distributed under the Creative Commons BY-SA 4.0 licence.
- **Downloaded by**: `scripts/download_data.py` from
  `http://www.blissymbolics.net/BCI-AV_2025-02-15/`.

## Blissary SVGs
- **Author**: Hannes Ljusås (hlridge), https://blissary.com
- **Used for**: the stroke-based vectors compiled into the `BlissaryFont`
  family (`scripts/build_blissary_font.py`, `data/raw/blissary/extracted/`).
- **Source repo for the ID crosswalk**:
  https://github.com/hlridge/bliss-blissary-bci-id-map (CC-BY-SA 4.0),
  integrated by `scripts/integrate_crosswalk.py` — attaches `blissary_id` and
  `bliss_svg_builder_code` to every record where a mapping exists
  (6,409/6,419 = 99.8% as of 2026-10-27).

## ISO/IEC JTC1/SC2/WG2 N5228 (Unicode proposal L2/23-138)
- **Author**: Michael Everson, "Proposal to encode Blissymbolics in Unicode"
  (document `23138-n5228-blissymbols.pdf`).
- **Used for**: the ~1,100 official proposed Unicode scalars (U+167xx block)
  parsed by `scripts/map_unicode.py` and recorded in `Unibliss.txt`.
  The remaining ~5,300 symbols are mapped to the **stable Plane-15 PUA**
  (`0xF0000 + BCI_ID`) as a transitional, redundancy-preserving encoding —
  official scalars always take precedence in downstream consumers.

## GloVe 6B (50d / 300d)
- **Authors**: Jeffrey Pennington, Richard Socher, Christopher D. Manning
  (Stanford), https://nlp.stanford.edu/projects/glove/
- **Licence: pre-trained vectors are PDDL v1.0 (public domain)** per
  https://nlp.stanford.edu/projects/glove/ — no attribution obligation;
  credited here as good practice. (The GloVe *code* is Apache 2.0; we ship
  only vectors.)
- **Used for**: the offline vector databases (`vocab.txt` + `vectors.bin`
  50d; regenerable `vectors300.bin` for bench work) powering the web sandbox
  semantic fallback, the resolver's semantic layer, and the blissbench
  runner. 50d files fetched from the JeremiahZ/glove mirror on Hugging Face;
  300d from stanfordnlp/glove.

## Blissary dictionary snapshot (blissbench data)
- **Authors**: Hannes Ljusås / Blissary, meanings drawing on BCI-AV
  (CC-BY-SA 4.0) — see `../blissbench/data/manifest.json` when present.

## ConceptNet 5.7
- **Authors**: Commonsense Computing Initiative contributors; maintained by
  Luminoso Technologies. https://conceptnet.io
- **Licence: CC BY-SA 4.0** (per-edge `license` fields vary; the aggregate is
  share-alike). Stored only in `symbol_hub.db.conceptnet_edges`
  (`scripts/load_conceptnet.py`, 1.97M edges from the 5.7.0 assertions dump)
  — **never exported into the shipped resolver asset**; keep separable.
  Loaded from
  https://s3.amazonaws.com/conceptnet/downloads/2019/edges/conceptnet-assertions-5.7.0.csv.gz

## sql.js
- **Author**: sql.js authors (Alon Zakai / kripken), https://sql.js
- **Licence: MIT.** Loaded from cdnjs by index.html, hub.html and ruby.html
  to run the resolver database in WebAssembly.

## Sibling tooling in the web pages
- Loaded from CDN at runtime; no redistribution occurs from this repository.

---
**Licence gap (deliberately unresolved):** this repository does not yet
declare a code licence. Choose one before public release; MPL-2.0 (used by
bliss-svg-builder and blissbench) or MIT are both compatible with the data
terms above. Data *derivatives* of BCI-AV/Blissary must respect those
upstream terms (share-alike where applicable).
