# WP1: The Unicode Datafile (Unibliss)

Goal: Programmatic compilation of the definitive `Unibliss.txt` character property dataset mapped against the BCI-AV 2025 release.

## Detailed Tasks

### [x] Task 1.1: Web Scraping and Ingestion
- [x] Auto-download the raw assets (implemented in `scripts/download_data.py`).
- [x] Parse BCI ID mappings and parse Excel Translations/Derivations.
- [x] Verify consistency between the SVG file names/IDs and Excel row IDs.
- [x] Clean and sanitize the SVGs (strip namespaces, canvas sizes, non-standard inline XML, and CSS).
- [x] Populate the relational data model (SQLite/JSON) mapping: `ID -> Cleaned SVG Path -> Lexical Translations`.

### [x] Task 1.2: Digital Sorting & Relational Weights
- [x] Read semantic composition strings (from Excel column `derivations`).
- [x] Parse components for each compound character (e.g. `['man', 'machine']`).
- [x] Formulate sorting weights so that characters sharing radical/base components are grouped in adjacent index spaces (e.g. semantic collation indexing).

### [x] Task 1.3: Generate Unicode Output
- [x] Cross-reference the 1,425 base characters of L2/23-138 and assign Unicode scalar blocks.
- [x] Write a script to output the data in the standard Unicode Character Database (UCD) format (`Unibliss.txt`).
- [x] Run a validator script asserting strict conformity to the Standard Unicode character property file formats.
