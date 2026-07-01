# Blissymbolics Digitization Project

This project focuses on the digitization, OpenType font engineering, data parsing, and input schema creation for Blissymbolics. It targets the **BCI Authorized Vocabulary of Blissymbolics (BCI-AV) 2025-02-15 Release** containing 6,183 active symbols.

## Directory Structure

```text
BlissFont/
├── .gitignore                # Git ignore rules for venv, raw data, databases, etc.
├── README.md                 # Project documentation
├── pyproject.toml            # Python dependencies (managed by uv)
├── data/
│   ├── raw/                  # [Ignored] Raw downloaded data (zip, xlsx, map txt)
│   └── processed/            # Processed databases, clean JSON graphs, normalized SVG paths
└── scripts/
    └── download_data.py      # Script to download and unpack BCI-AV 2025 data files
```

## Getting Started

### 1. Requirements

* **Python 3.10+**
* [**uv**](https://github.com/astral-sh/uv) (fast Python packaging tool)

If `uv` is not installed on your system, you can install it via:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installation

Install dependencies and create the virtual environment by running:
```bash
uv sync
```

### 3. Fetching Raw Datasets

Run the bootstrap script to scrape and download the BCI-AV 2025 data, then extract the vector graphics:
```bash
uv run python scripts/download_data.py
```

This will populate:
* `data/raw/bliss_svg_id.zip` (original ZIP)
* `data/raw/svgs/` (extracted clean/original SVG vector glyphs)
* `data/raw/BCI-AV_SKOG_2025-02-15_ID_to_gloss_map.txt` (ID to gloss mappings)
* `data/raw/BCI-AV_SKOG_2025-02-15_derivations_translations.xlsx` (Excel sheets containing language translations & derivations formula)

## Key Dependencies

* `fonttools`: Library for manipulating fonts (parsing, building glyph outlines, compiling OpenType features).
* `pandas` & `openpyxl`: For loading, cleaning, and indexing the BCI-AV Excel datasets.
* `requests`: For programmatically fetching external web resources.
