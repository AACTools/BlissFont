#!/usr/bin/env python3
import os
import re
import sqlite3
import json
import pypdf

PDF_PATH = os.path.join("data", "raw", "23138-n5228-blissymbols.pdf")
DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")

def parse_nameslist_pdf():
    # Read the 103-page PDF and extract code points and BCI ID associations
    reader = pypdf.PdfReader(PDF_PATH)
    print(f"Reading names list annotations from: {PDF_PATH}")
    
    # Matches character line: e.g. "16543 BLISSYMBOL SISTER OF MOTHER"
    char_re = re.compile(r'^([10][0-9A-F]{4})\s+.*?BLISSYMBOL\s+(.+)$')
    
    metadata = {}
    current_cp = None
    
    for idx, page in enumerate(reader.pages):
        # Names list resides between page 31 and 66
        if idx < 30 or idx > 66:
            continue
        text = page.extract_text() or ''
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            match = char_re.match(line)
            if match:
                current_cp = match.group(1)
                metadata[current_cp] = {
                    "hex_cp": current_cp,
                    "bci_av": None,
                    "n1866": None,
                    "msbi": None,
                    "radical": 0,
                    "synonyms": [],
                    "notes": []
                }
            elif current_cp and line.startswith("•"):
                # Parse bullet points
                if "BCI-AV-" in line:
                    parts = line.split("BCI-AV-")
                    metadata[current_cp]["bci_av"] = parts[1].strip()
                elif "N1866-" in line:
                    parts = line.split("N1866-")
                    metadata[current_cp]["n1866"] = parts[1].strip()
                elif "MSBI-r-" in line:
                    parts = line.split("MSBI-r-")
                    metadata[current_cp]["msbi"] = parts[1].strip()
                elif "used as a radical" in line:
                    metadata[current_cp]["radical"] = 1
                else:
                    metadata[current_cp]["notes"].append(line.replace("•", "").strip())
            elif current_cp and line.startswith("="):
                # Parse synonym gloss annotations
                syn = line.replace("=", "").strip()
                metadata[current_cp]["synonyms"].append(syn)
                
    print(f"Parsed metadata for {len(metadata)} characters from PDF.")
    return metadata

def update_database_and_json(metadata):
    print("Updating database and JSON mappings...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Ensure columns exist in symbols table
    cursor.execute("PRAGMA table_info(symbols)")
    cols = [col[1] for col in cursor.fetchall()]
    
    new_cols = {
        "n1866_ref": "TEXT",
        "msbi_ref": "TEXT",
        "is_radical": "INTEGER DEFAULT 0",
        "synonym_annotations": "TEXT"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE symbols ADD COLUMN {col_name} {col_type}")
            conn.commit()

    # Load JSON file
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            records = json.load(f)
    else:
        records = []

    # Map Hex code points and BCI IDs to metadata
    updated_db_count = 0
    updated_json_count = 0
    
    for val in metadata.values():
        bci_av = val["bci_av"]
        if not bci_av:
            continue
            
        bci_id = str(int(bci_av)) if bci_av.isdigit() else bci_av
        synonyms_str = json.dumps(val["synonyms"], ensure_ascii=False)
        
        # Update SQLite table
        # Matches direct BCI ID or variant prefixes
        query = """
            UPDATE symbols 
            SET n1866_ref = ?, msbi_ref = ?, is_radical = ?, synonym_annotations = ?
            WHERE bci_id = ? OR bci_id = ? OR bci_id = ? OR bci_id = ?
        """
        cursor.execute(query, (
            val["n1866"],
            val["msbi"],
            val["radical"],
            synonyms_str,
            bci_id,
            f"c-{bci_id}",
            f"m-{bci_id}",
            f"b-{bci_id}"
        ))
        if cursor.rowcount > 0:
            updated_db_count += 1
            
        # Update JSON record
        for rec in records:
            r_id = rec["bci_id"]
            if r_id == bci_id or r_id == f"c-{bci_id}" or r_id == f"m-{bci_id}" or r_id == f"b-{bci_id}":
                rec["n1866_ref"] = val["n1866"]
                rec["msbi_ref"] = val["msbi"]
                rec["is_radical"] = val["radical"]
                rec["synonym_annotations"] = val["synonyms"]
                updated_json_count += 1
                
    conn.commit()
    conn.close()
    
    # Save JSON back
    if records:
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
            
    print(f"Updated SQLite database: {updated_db_count} records.")
    print(f"Updated JSON character records: {updated_json_count} records.")

def main():
    metadata = parse_nameslist_pdf()
    if metadata:
        update_database_and_json(metadata)
    else:
        print("Error: No metadata extracted.")

if __name__ == "__main__":
    main()
