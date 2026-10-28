# NOTICE — Data sources and attribution

This project builds on top of several open datasets and prior work. If you
redistribute compiled fonts, databases, or derived data, carry these credits
and the respective licence terms with them.

## BCI Authorized Vocabulary of Blissymbolics (BCI-AV) 2025-02-15
- **Author**: Blissymbolics Communication International (BCI),
  https://www.blissymbolics.org — symbol files at
  https://blissymbolics.org/index.php/symbol-files
- **Used for**: the 6,183 active symbols (6,419 glyph records) — English and
  16-language glosses, derivations, POS classes, and the source SVG vectors of
  the `BlissFont` outline family. The *terms of the BCI-AV release apply* to
  this data; capture and honour them before redistributing (see task T-106 in
  the project brief).
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

## GloVe 6B (50d)
- **Authors**: Jeffrey Pennington, Richard Socher, Christopher D. Manning
  (Stanford), https://nlp.stanford.edu/projects/glove/
- **Used for**: the offline 100k-word vector database (`vocab.txt` +
  `vectors.bin`, float16) powering the web sandbox semantic fallback and the
  blissbench `blissfont-compose` runner. Built by `scripts/build_vector_db.py`
  from the JeremiahZ/glove mirror on Hugging Face.

## Blissary dictionary snapshot (blissbench data)
- **Authors**: Hannes Ljusås / Blissary, meanings drawing on BCI-AV
  (CC-BY-SA 4.0) — see `../blissbench/data/manifest.json` when present.

---
**Licence gap (deliberately unresolved):** this repository does not yet
declare a code licence. Choose one before public release; MPL-2.0 (used by
bliss-svg-builder and blissbench) or MIT are both compatible with the data
terms above. Data *derivatives* of BCI-AV/Blissary must respect those
upstream terms (share-alike where applicable).
