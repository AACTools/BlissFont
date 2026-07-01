# WP2: Font Engineering & OpenType Smart Rules

Goal: Generation of a fully responsive `.otf` / `.woff2` font containing complex diacritic anchors and contextual layout tables.

## Detailed Tasks

### [ ] Task 2.1: Automatic Vector Normalization
- [ ] Set up python scripts utilizing `defcon` and `fontTools`.
- [ ] Parse the 6,183 cleaned SVG graphics.
- [ ] Scale contours to standard UPM (Units Per Em, e.g., 1000).
- [ ] Generate unified font glyph contours and output a baseline `.ufo` or `.otf`.

### [ ] Task 2.2: OpenType Glyph Positioning (GPOS) Engine Injection
- [ ] Parse coordinates (anchor placements) from the **Human Calibration & Review Tool**.
- [ ] Define the anchor points for `top_diacritic` and `bottom_diacritic` per glyph.
- [ ] Programmatically compile and inject Mark-to-Base / Mark-to-Mark GPOS lookup tables into the font header.

### [ ] Task 2.3: Contextual Substitution (GSUB) for Mirrored Layouts
- [ ] Define directional mirroring rules (e.g., symbols that need to reflect when in RTL text layouts).
- [ ] Write a `.fea` (Adobe Font Feature) layout script containing GSUB lookup rules.
- [ ] Programmatically compile the `.fea` rules into the final `.otf` / `.woff2` binaries.
