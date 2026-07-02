# Blissymbolics Digitization Master TODO

This file tracks the overarching milestones and tasks for the Blissymbolics Digitization Project. For granular task checklists, see the dedicated Work Package (WP) TODO lists.

## Project Roadmap & Status

- [x] **[WP1: The Unicode Datafile (Unibliss)](./todo/wp1_unibliss.md)**
  - [x] Task 1.1: Web Scraping and Ingestion
  - [x] Task 1.2: Digital Sorting & Relational Weights
  - [x] Task 1.3: Generate Unicode Output (Unibliss.txt)
- [x] **[WP2: Font Engineering & OpenType Smart Rules](./todo/wp2_font_engineering.md)**
  - [x] Task 2.1: Automatic Vector Normalization (UPM 1000 contours)
  - [x] Task 2.2: OpenType Glyph Positioning (GPOS) Engine Injection
  - [x] Task 2.3: Contextual Substitution (GSUB) for Mirrored Layouts
- [x] **[WP3: Cross-Platform Input Method Schema (RIME Engine)](./todo/wp3_rime_input.md)**
  - [x] Task 3.1: Programmatic Translation Schema & Dictionary Generation (`blissymbols.dict.yaml`)
  - [x] Task 3.2: RIME Blueprint Configuration (`blissymbols.schema.yaml`)
  - [x] Task 3.3: Accessibility Tuning & Distribution Packages (`Weasel`, `Squirrel`, `ibus-rime`)

---

## Current Bootstrapping & Setup Status

- [x] Python virtual environment initialization with `uv`
- [x] External dataset downloads (BCI-AV 2025-02-15)
- [x] Initial dependency setup (`fonttools`, `pandas`, `requests`, `openpyxl`)
- [x] Verification of downloaded assets (Excel, TXT, SVG Zip)
