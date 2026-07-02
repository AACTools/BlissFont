# WP2: Font Engineering & OpenType Smart Rules

Goal: Generation of a fully responsive `.otf` / `.woff2` font containing complex diacritic anchors and contextual layout tables.

## Detailed Tasks

### [x] Task 2.1: Automatic Vector Normalization
- [x] Set up python scripts utilizing `defcon` and `fontTools`.
- [x] Parse the 6,183 cleaned SVG graphics.
- [x] Scale contours to standard UPM (Units Per Em, e.g., 1000).
- [x] Generate unified font glyph contours and output a baseline `.ufo` or `.otf`.

### [x] Task 2.2: OpenType Glyph Positioning (GPOS) Engine Injection
- [x] Parse coordinates (anchor placements) from the **Human Calibration & Review Tool**.
- [x] Define the anchor points for `top_diacritic` and `bottom_diacritic` per glyph.
- [x] Programmatically compile and inject Mark-to-Base / Mark-to-Mark GPOS lookup tables into the font header.

### [x] Task 2.3: Contextual Substitution (GSUB) for Mirrored Layouts
- [x] Define directional mirroring rules (e.g., symbols that need to reflect when in RTL text layouts).
- [x] Write a `.fea` (Adobe Font Feature) layout script containing GSUB lookup rules.
- [x] Programmatically compile the `.fea` rules into the final `.otf` / `.woff2` binaries.
