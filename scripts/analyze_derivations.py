#!/usr/bin/env python3
import os
import sqlite3
import json
from collections import defaultdict

DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")

# Define the order of the 29 base Bliss-letters (radicals) from Everson's proposal
# These will act as our primary collation keys.
BASE_RADICALS_ORDER = [
    "wavy line", "heart", "cross hatch", "building", "ear", "arrow", "wheel",
    "large circle", "small circle", "half circle", "quarter circle", "parenthesis",
    "square", "rectangle", "open square", "open rectangle", "right triangle",
    "dot", "right angle", "line on a base", "cross", "isosceles triangle",
    "symmetric acute angle", "animals", "asymmetric acute angle",
    "horizontal line", "vertical line", "slanted line", "diagonal line"
]

def build_synonym_lookup(cursor):
    # Retrieve all symbols and build a lookup dict from english glosses/synonyms to bci_id
    cursor.execute("SELECT bci_id, english_gloss FROM symbols")
    gloss_map = {}
    for bci_id, gloss in cursor.fetchall():
        if gloss:
            for term in gloss.split(','):
                term_clean = term.strip().lower()
                if term_clean:
                    gloss_map[term_clean] = bci_id
    return gloss_map

def resolve_components():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create table for resolved derivations
    cursor.execute("DROP TABLE IF EXISTS resolved_derivations")
    cursor.execute("""
    CREATE TABLE resolved_derivations (
        bci_id TEXT,
        component_bci_id TEXT,
        FOREIGN KEY(bci_id) REFERENCES symbols(bci_id),
        FOREIGN KEY(component_bci_id) REFERENCES symbols(bci_id)
    )""")
    
    gloss_map = build_synonym_lookup(cursor)
    
    # Let's map some common descriptive terms that appear in derivations to base symbols
    manual_mappings = {
        "wagon": gloss_map.get("vehicle"),
        "baby": gloss_map.get("child"),
        "pictograph of a steering wheel": gloss_map.get("wheel"),
        "steering wheel": gloss_map.get("wheel"),
        "house": gloss_map.get("building"),
        "fear": gloss_map.get("afraid"),
        "fright": gloss_map.get("afraid"),
        "concern": gloss_map.get("afraid"),
        "observation": gloss_map.get("to observe"),
        "intensity": gloss_map.get("much"),
        "description indicator": gloss_map.get("modifier"),
        "action indicator": gloss_map.get("verb"),
        "plural indicator": gloss_map.get("plural"),
        "water_earth": gloss_map.get("water"),
        "water_middle": gloss_map.get("water"),
        "water_sky": gloss_map.get("water"),
    }
    
    cursor.execute("SELECT bci_id, component_term FROM derivations")
    raw_derivs = cursor.fetchall()
    
    unresolved = set()
    resolved_count = 0
    
    for bci_id, term in raw_derivs:
        comp_id = None
        if term in gloss_map:
            comp_id = gloss_map[term]
        elif term in manual_mappings:
            comp_id = manual_mappings[term]
        else:
            # Try fuzzy matching: check if term is a substring of any synonym, or vice versa
            for synonym, s_id in gloss_map.items():
                if term in synonym or synonym in term:
                    comp_id = s_id
                    break
                    
        if comp_id:
            cursor.execute("""
                INSERT INTO resolved_derivations (bci_id, component_bci_id)
                VALUES (?, ?)
            """, (bci_id, comp_id))
            resolved_count += 1
        else:
            unresolved.add(term)
            
    print(f"Resolved {resolved_count} derivation component links.")
    print(f"Unresolved unique component terms: {len(unresolved)}")
    # If small, we can print some unresolved terms
    if len(unresolved) > 0:
        print("Sample unresolved terms:", list(unresolved)[:15])
        
    conn.commit()
    conn.close()

def calculate_collation_weights():
    # We will compute a collation index score for each symbol based on its radical composition
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create collation table
    cursor.execute("DROP TABLE IF EXISTS collation")
    cursor.execute("""
    CREATE TABLE collation (
        bci_id TEXT PRIMARY KEY,
        collation_weight INTEGER,
        FOREIGN KEY(bci_id) REFERENCES symbols(bci_id)
    )""")
    
    # 1. Fetch resolved derivations mapping
    cursor.execute("SELECT bci_id, component_bci_id FROM resolved_derivations")
    deriv_map = defaultdict(list)
    for bci_id, comp_id in cursor.fetchall():
        deriv_map[bci_id].append(comp_id)
        
    # 2. Fetch all symbols
    cursor.execute("SELECT bci_id, english_gloss, category FROM symbols")
    all_symbols = cursor.fetchall()
    
    # Map primary English glosses to base radical indices for sorting
    radical_to_idx = {rad: idx for idx, rad in enumerate(BASE_RADICALS_ORDER)}
    
    # We can write a helper to find the primary radical of a symbol
    # (either itself if it's a radical, or the first radical in its components)
    def get_primary_radical_idx(bci_id, english_gloss, visited=None):
        if visited is None:
            visited = set()
        if bci_id in visited:
            return len(BASE_RADICALS_ORDER) # circular dependency fallback
        visited.add(bci_id)
        
        gloss_clean = english_gloss.lower().strip()
        if gloss_clean in radical_to_idx:
            return radical_to_idx[gloss_clean]
            
        components = deriv_map.get(bci_id, [])
        if components:
            # Check components recursively
            for comp_id in components:
                cursor.execute("SELECT english_gloss FROM symbols WHERE bci_id=?", (comp_id,))
                res = cursor.fetchone()
                if res:
                    idx = get_primary_radical_idx(comp_id, res[0], visited)
                    if idx < len(BASE_RADICALS_ORDER):
                        return idx
                        
        return len(BASE_RADICALS_ORDER) # miscellaneous fallback at the end

    symbol_weights = []
    for bci_id, english, category in all_symbols:
        primary_rad_idx = get_primary_radical_idx(bci_id, english)
        
        # Formulate weight: primary_rad_idx * 10000 + number of components * 100 + numeric ID (for stable sorting)
        num_components = len(deriv_map.get(bci_id, []))
        try:
            numeric_id = int(bci_id)
        except ValueError:
            numeric_id = 99999
            
        weight = primary_rad_idx * 1000000 + num_components * 100000 + numeric_id
        symbol_weights.append((bci_id, weight))
        
    # Sort symbols by weight to assign sequential indexes
    symbol_weights.sort(key=lambda x: x[1])
    
    for rank, (bci_id, weight) in enumerate(symbol_weights):
        cursor.execute("INSERT INTO collation (bci_id, collation_weight) VALUES (?, ?)", (bci_id, rank))
        
    print(f"Calculated lexicographical collation index for {len(symbol_weights)} symbols.")
    
    conn.commit()
    conn.close()
    
    # 3. Update the processed JSON file with weight rankings
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            records = json.load(f)
            
        weight_lookup = {bci_id: rank for rank, (bci_id, w) in enumerate(symbol_weights)}
        
        # Inject weight into derivations list (or we can inject custom sorting weights)
        for rec in records:
            bci_id = rec["bci_id"]
            rec["collation_weight"] = weight_lookup.get(bci_id, 99999)
            
        # Re-sort JSON records by collation weight for clean output order
        records.sort(key=lambda x: x["collation_weight"])
        
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        print("Updated and sorted JSON character records with collation weights.")

if __name__ == "__main__":
    resolve_components()
    calculate_collation_weights()
