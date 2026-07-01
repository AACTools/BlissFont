#!/usr/bin/env python3
import os
import sqlite3
import re
import json

DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
DICT_PATH = os.path.join("data", "processed", "blissymbols.dict.yaml")

def clean_gloss_for_rime(gloss):
    if not gloss or not isinstance(gloss, str):
        return []
    # Split by comma for synonyms
    syns = gloss.split(',')
    results = []
    for s in syns:
        # Strip parentheses and their contents, e.g. "zero_(digit)" -> "zero"
        s_clean = re.sub(r'\([^)]*\)', '', s).strip()
        # Keep only letters and digits
        s_letters = re.sub(r'[^a-zA-Z0-9]', '', s_clean).lower()
        if s_letters:
            results.append(s_letters)
            
        # Also allow typing with underscores if someone wants it
        s_underscore = re.sub(r'[^a-zA-Z0-9_]', '', s.strip().replace(' ', '_')).lower()
        if s_underscore and s_underscore != s_letters:
            results.append(s_underscore)
    return list(set(results))

def extract_key_sequence(winbliss):
    if not winbliss or not isinstance(winbliss, str):
        return ""
    # Remove trailing format characters like %£ or *%£
    clean = re.sub(r'[*%£]+$', '', winbliss.strip())
    # Split by &
    segments = clean.split('&')
    keys = []
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        # Get character before #
        key = seg.split('#')[0].strip()
        if key:
            keys.append(key.lower())
    return "".join(keys)

def main():
    if not os.path.exists(DB_PATH) or not os.path.exists(JSON_PATH):
        print("Error: Compiled vocabulary assets not found.")
        return
        
    print("Loading SQLite database and JSON rankings...")
    # Load JSON records to get stable collation rank for PUA mapping
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)
        
    id_to_rank = {r["bci_id"]: idx for idx, r in enumerate(records)}
    

    
    import pandas as pd
    excel_path = os.path.join("data", "raw", "BCI-AV_SKOG_2025-02-15_derivations_translations.xlsx")
    print(f"Reading WinBliss strings from Excel: {excel_path}")
    df = pd.read_excel(excel_path)
    
    dict_lines = [
        "# Rime dictionary",
        "# encoding: utf-8",
        "",
        "---",
        "name: blissymbols",
        "version: \"0.1\"",
        "sort: by_weight",
        "use_preset_vocabulary: false",
        "...",
        ""
    ]
    
    entries_count = 0
    
    for idx, row in df.iterrows():
        bci_id = str(row['BCI-AV#']).strip()
        english = str(row.get('English', '')).strip()
        swedish = str(row.get('Swedish', '')).strip() if pd.notna(row.get('Swedish')) else ""
        winbliss = str(row.get('WinBliss', '')).strip() if pd.notna(row.get('WinBliss')) else ""
        
        # Get character symbols
        char_pua = ""
        rank = id_to_rank.get(bci_id)
        if rank is not None:
            char_pua = chr(0xE000 + rank)
            
        char_uni = ""
        p_uni = records[rank].get("proposed_unicode") if rank is not None else None
        if p_uni and p_uni.startswith("U+"):
            try:
                char_uni = chr(int(p_uni[2:], 16))
            except ValueError:
                pass
                
        # We output dictionary mappings for both the PUA character and the proposed Unicode character (if available)
        targets = [c for c in [char_pua, char_uni] if c]
        
        for char in targets:
            # 1. Everson direct key sequence mapping
            key_seq = extract_key_sequence(winbliss)
            if key_seq:
                dict_lines.append(f"{char}\t{key_seq}\t100")
                entries_count += 1
                
            # 2. English gloss transliteration lookups
            eng_keys = clean_gloss_for_rime(english)
            for k in eng_keys:
                dict_lines.append(f"{char}\t{k}\t10")
                entries_count += 1
                
            # 3. Swedish gloss transliteration lookups
            sv_keys = clean_gloss_for_rime(swedish)
            for k in sv_keys:
                dict_lines.append(f"{char}\t{k}\t5")
                entries_count += 1
                
    print(f"Writing structured RIME dictionary: {DICT_PATH}")
    with open(DICT_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dict_lines))
        
    print(f"RIME dictionary build complete! Wrote {entries_count} mapping entries.")

if __name__ == "__main__":
    main()
