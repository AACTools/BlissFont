#!/usr/bin/env python3
"""
Merge ALL languages (+ WinBliss input sequences) from the BCI-AV 2025-02-15
derivations spreadsheet into bliss_character_data.json.

The DB builder only carried 5 gloss languages (en/sv/de/nl/fr); the source
xlsx actually has 19 languages, per-language derivation explanations, POS
class colour, and WinBliss keyboard sequences. BlissFont's JSON is the source
of truth for the web app, RIME dict, semantic DB, and symbol hub — so this
fills the gap at the root.

Usage:
    uv run python scripts/merge_all_languages.py   # xlsx auto-downloaded if absent
"""
import json
import os
import urllib.request

import openpyxl

RAW = os.path.join("data", "raw")
XLSX = os.path.join(RAW, "BCI-AV_derivations.xlsx")
XLSX_URL = (
    "http://www.blissymbolics.net/BCI-AV_2025-02-15/"
    "BCI-AV_SKOG_2025-02-15_%28en%2Bsv%2Bno%2Bfi%2Bhu%2Bde%2Bnl%2Baf%2Bru%2Bis"
    "%2Blt%2Blv%2Bpo%2Bfr%2Bes%2Bpt%2Bit%2Bdk%29%2Bderivations_8483-29642.xlsx"
)
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")

# spreadsheet column name -> our gloss key
LANG_MAP = {
    "English": "en", "Swedish": "sv", "Norwegian": "no", "Finnish": "fi",
    "Hungarian": "hu", "German": "de", "Dutch": "nl", "Afrikaans": "af",
    "Russian": "ru", "Icelandic": "is", "Lithuanian": "lt", "Latvian": "lv",
    "Polish": "pl", "French": "fr", "Spanish": "es", "Portugese": "pt",
    "Italian": "it", "Danish": "da",
}


def main() -> None:
    if not os.path.exists(XLSX):
        os.makedirs(RAW, exist_ok=True)
        print(f"Downloading {XLSX_URL}")
        urllib.request.urlretrieve(XLSX_URL, XLSX)
    print(f"Reading {XLSX}")
    wb = openpyxl.load_workbook(XLSX, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h is not None else "" for h in next(rows)]

    col_idx = {name: i for i, name in enumerate(header)}
    lang_cols = {k: col_idx[k] for k in LANG_MAP if k in col_idx}
    winbliss_i = col_idx.get("WinBliss")
    expl_i = col_idx.get("Derivation - explanation")
    print(f"Language columns found: {sorted(lang_cols)}")

    sheet = {}
    for row in rows:
        if row[0] is None:
            continue
        bci = str(row[0]).strip()
        entry = {}
        for col_name, i in lang_cols.items():
            v = row[i] if i < len(row) else None
            if v is not None and str(v).strip():
                entry[LANG_MAP[col_name]] = str(v).strip()
        if winbliss_i is not None and winbliss_i < len(row) and row[winbliss_i]:
            entry["_winbliss"] = str(row[winbliss_i]).strip()
        if expl_i is not None and expl_i < len(row) and row[expl_i]:
            entry["_expl_en"] = str(row[expl_i]).strip()[:500]
        sheet[bci] = entry
    print(f"Spreadsheet rows: {len(sheet)}")

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records = json.load(f)

    matched, langs_added, winbliss_added = 0, 0, 0
    lang_totals = {}
    unmatched = []
    for r in records:
        src = sheet.get(r["bci_id"])
        if not src:
            # tolerate prefixed variants (c-/m-/b-) recorded by the DB builder
            base = r["bci_id"].split("-", 1)[-1]
            src = sheet.get(base)
        if not src:
            unmatched.append(r["bci_id"])
            continue
        matched += 1
        r.setdefault("glosses", {})
        for lang, val in src.items():
            if lang == "_winbliss":
                if not r.get("winbliss"):
                    r["winbliss"] = val
                    winbliss_added += 1
            elif lang == "_expl_en":
                if not r.get("explanation_en"):
                    r["explanation_en"] = val
            else:
                if not r["glosses"].get(lang):
                    r["glosses"][lang] = val
                    lang_totals[lang] = lang_totals.get(lang, 0) + 1
                    langs_added += 1

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Matched {matched}/{len(records)} records ({len(unmatched)} unmatched)")
    print(f"New gloss values added: {langs_added} across {len(lang_totals)} languages")
    for lang in sorted(lang_totals):
        print(f"  {lang}: +{lang_totals[lang]}")
    print(f"WinBliss sequences added: {winbliss_added}")
    if unmatched[:10]:
        print("Sample unmatched ids:", unmatched[:10])


if __name__ == "__main__":
    main()
