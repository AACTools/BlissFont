#!/usr/bin/env python3
import os
import re
import sqlite3
import json
import pypdf

PDF_PATH = os.path.join("data", "raw", "23138-n5228-blissymbols.pdf")
DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
OUTPUT_TXT_PATH = os.path.join("data", "processed", "Unibliss.txt")

def parse_unicode_pdf():
    # Read the 103-page PDF and extract code points and BCI ID associations
    reader = pypdf.PdfReader(PDF_PATH)
    print(f"Reading proposed Unicode list from: {PDF_PATH}")
    
    mapping = {}
    
    # Matches hex code point definition line, e.g. "164E0  BLISSYMBOL SHIELD"
    cp_re = re.compile(r'^([10][0-9A-F]{4})\s+.*?BLISSYMBOL\s+(.+)$')
    # Matches bullet point with BCI reference: e.g., "• BCI-AV-14442"
    bci_re = re.compile(r'•\s+BCI-AV-([a-zA-Z0-9_-]+)')
    
    current_cp = None
    current_name = None
    
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ''
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            parts = line.split()
            # If line starts with a 5-digit hex code in plane 1 (1XXXX) or PUA (EXXXX)
            if len(parts) >= 3 and len(parts[0]) == 5 and all(c in '0123456789ABCDEF' for c in parts[0]):
                if "BLISSYMBOL" in line:
                    current_cp = parts[0]
                    name_parts = line.split("BLISSYMBOL", 1)
                    if len(name_parts) == 2:
                        current_name = "BLISSYMBOL " + name_parts[1].strip()
                    else:
                        current_name = "BLISSYMBOL " + " ".join(parts[2:])
            elif bci_re.search(line):
                bci_match = bci_re.search(line)
                bci_val = bci_match.group(1).strip()
                # Normalize BCI ID by stripping leading zeros if it is numeric
                bci_val_norm = str(int(bci_val)) if bci_val.isdigit() else bci_val
                if current_cp:
                    # Clean up the ID
                    mapping[bci_val_norm] = {
                        "unicode": f"U+{current_cp}",
                        "hex_cp": current_cp,
                        "name": current_name
                    }
                    
    print(f"Parsed {len(mapping)} character mappings from PDF.")
    return mapping

def update_database_and_json(mappings):
    print("Updating database and JSON mappings...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Ensure symbols table has proposed_unicode column
    # Check if proposed_unicode column already exists
    cursor.execute("PRAGMA table_info(symbols)")
    cols = [col[1] for col in cursor.fetchall()]
    if "proposed_unicode" not in cols:
        cursor.execute("ALTER TABLE symbols ADD COLUMN proposed_unicode TEXT")
        conn.commit()
        
    # 2. Update database values
    updated_db_count = 0
    for bci_id, val in mappings.items():
        # First update direct numeric match
        cursor.execute("UPDATE symbols SET proposed_unicode = ? WHERE bci_id = ?", (val["unicode"], bci_id))
        if cursor.rowcount > 0:
            updated_db_count += cursor.rowcount
        else:
            # Try mapping variant formats like prefix c- or suffix variants
            cursor.execute("UPDATE symbols SET proposed_unicode = ? WHERE bci_id = ?", (val["unicode"], f"c-{bci_id}"))
            cursor.execute("UPDATE symbols SET proposed_unicode = ? WHERE bci_id = ?", (val["unicode"], f"m-{bci_id}"))
            cursor.execute("UPDATE symbols SET proposed_unicode = ? WHERE bci_id = ?", (val["unicode"], f"b-{bci_id}"))
            if cursor.rowcount > 0:
                updated_db_count += cursor.rowcount

    conn.commit()
    conn.close()
    print(f"Updated {updated_db_count} rows in SQLite symbols table.")
    
    # 3. Update processed JSON file
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            records = json.load(f)
            
        json_updates = 0
        for rec in records:
            bci_id = rec["bci_id"]
            # Look up by direct BCI-AV ID
            map_info = mappings.get(bci_id)
            if not map_info:
                # Look up with variant prefixes
                for prefix in ["c-", "m-", "b-"]:
                    if f"{prefix}{bci_id}" in mappings:
                        map_info = mappings[f"{prefix}{bci_id}"]
                        break
            if not map_info:
                # Look up strip prefix from BCI-AV mapping
                if bci_id.startswith("c-") and bci_id[2:] in mappings:
                    map_info = mappings[bci_id[2:]]
                    
            if map_info:
                rec["proposed_unicode"] = map_info["unicode"]
                json_updates += 1
                
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        print(f"Updated proposed_unicode fields in JSON character records: {json_updates} matches.")

def generate_unibliss_txt(mappings):
    print(f"Generating Unicode property file: {OUTPUT_TXT_PATH}")
    
    # Conforms to standard UnicodeData.txt format
    # Fields:
    # 1. CodePoint (hex)
    # 2. Name
    # 3. General Category (Lo = Letter Other, Mn = Mark Nonspacing, etc.)
    # 4. Canonical Combining Class (0 for spacing characters)
    # 5. Bidi Class (L = Left-to-Right)
    # 6. Decomposition
    # 7. Decimal digit value
    # 8. Digit value
    # 9. Numeric value
    # 10. Bidi Mirrored (N by default, Y for directional symbols)
    # 11. Unicode 1.0 Name (empty)
    # 12. ISO Comment (empty)
    # 13. Simple Uppercase (empty)
    # 14. Simple Lowercase (empty)
    # 15. Simple Titlecase (empty)
    
    # Sort mappings by hex code point
    sorted_cps = sorted(mappings.values(), key=lambda x: x["hex_cp"])
    
    with open(OUTPUT_TXT_PATH, 'w', encoding='utf-8') as f:
        for val in sorted_cps:
            cp = val["hex_cp"]
            name = val["name"].upper()
            
            # Determine General Category:
            # Indicators are combining marks, so they get 'Mn' (Mark, Nonspacing) or 'Sk'
            category = "Lo"  # default to Letter, Other (spacing character)
            if "INDICATOR" in name or "COMBINING" in name:
                category = "Mn"
                
            mirrored = "N"
            # Mark certain directional characters as mirrored
            if "ARROW" in name or "REVERSED" in name or "LEFT" in name or "RIGHT" in name:
                mirrored = "Y"
                
            line = f"{cp};{name};{category};0;L;;;;;{mirrored};;;;;\n"
            f.write(line)
            
    print("Unibliss.txt property file written successfully!")

def main():
    mappings = parse_unicode_pdf()
    if mappings:
        update_database_and_json(mappings)
        generate_unibliss_txt(mappings)
    else:
        print("Error: No mappings extracted.")

if __name__ == "__main__":
    main()
