#!/usr/bin/env python3
import os
import re
import sqlite3
import json
import pandas as pd
import xml.etree.ElementTree as ET
from collections import defaultdict

RAW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
PROCESSED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
SVG_DIR = os.path.join(RAW_DIR, "svgs", "bliss_svg_id")

DB_PATH = os.path.join(PROCESSED_DIR, "bliss_vocabulary.db")
JSON_PATH = os.path.join(PROCESSED_DIR, "bliss_character_data.json")

# Map Excel columns to language codes
LANGUAGES = {
    "English": "en",
    "Swedish": "sv",
    "Norwegian": "no",
    "Finnish": "fi",
    "Hungarian": "hu",
    "German": "de",
    "Dutch": "nl",
    "Afrikaans": "af",
    "Russian": "ru",
    "Icelandic": "is",
    "Lithuanian": "lt",
    "Latvian": "lv",
    "Polish": "po",
    "French": "fr",
    "Spanish": "es",
    "Portugese": "pt",
    "Italian": "it",
    "Danish": "dk"
}

def parse_css_styles(style_text):
    # Parses CSS declarations like '.pen1 { stroke: rgb(0,0,0); stroke-width: 7; }'
    # Returns a dict of class names to style properties dict
    styles = {}
    if not style_text:
        return styles
    rules = re.findall(r'\.([a-zA-Z0-9_-]+)\s*\{([^}]+)\}', style_text)
    for class_name, decls in rules:
        styles[class_name] = {}
        for decl in decls.split(';'):
            decl = decl.strip()
            if not decl:
                continue
            if ':' in decl:
                prop, val = decl.split(':', 1)
                styles[class_name][prop.strip()] = val.strip()
    return styles

def sanitize_color(color_str):
    # Convert rgb(r,g,b) to hex or simple names
    if not color_str:
        return "none"
    rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color_str)
    if rgb_match:
        r, g, b = map(int, rgb_match.groups())
        if r == 255 and g == 255 and b == 255:
            return "white"
        if r == 0 and g == 0 and b == 0:
            return "black"
        return f"#{r:02x}{g:02x}{b:02x}"
    return color_str

def sanitize_svg(svg_path):
    # Sanitizes the SVG: inlines CSS classes, strips namespaces and boilerplate,
    # and returns a clean inline SVG string and the viewBox dimensions.
    if not os.path.exists(svg_path):
        return None, None
        
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # Get viewBox dimensions
        view_box = root.attrib.get('viewBox')
        vb_w, vb_h = 308.0, 324.0 # default values if not found
        if view_box:
            nums = [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', view_box)]
            if len(nums) == 4:
                vb_w, vb_h = nums[2], nums[3]

        # Extract styles
        styles = {}
        style_elem = root.find('.//{http://www.w3.org/2000/svg}style')
        if style_elem is not None:
            styles = parse_css_styles(style_elem.text)

        # Build new root
        new_root = ET.Element('svg', {
            'viewBox': f"0 0 {int(vb_w)} {int(vb_h)}"
        })
        
        # We iterate over all drawable elements
        for elem in root.iter():
            tag = elem.tag.split('}')[-1]
            if tag in ['line', 'circle', 'ellipse', 'rect', 'path', 'polygon', 'polyline']:
                new_attrs = {}
                
                # Copy coordinates and geometric parameters
                for attr, val in elem.attrib.items():
                    if attr not in ['class', 'style']:
                        new_attrs[attr] = val
                
                # Apply inlined styles from class
                cls = elem.attrib.get('class')
                if cls and cls in styles:
                    for prop, val in styles[cls].items():
                        if prop == 'stroke':
                            new_attrs['stroke'] = sanitize_color(val)
                        elif prop == 'fill':
                            new_attrs['fill'] = sanitize_color(val)
                        elif prop in ['stroke-width', 'stroke-linecap', 'stroke-linejoin']:
                            new_attrs[prop] = val

                # Merge direct attributes (they override class)
                for prop in ['fill', 'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin']:
                    if prop in elem.attrib:
                        new_attrs[prop] = sanitize_color(elem.attrib[prop]) if prop in ['fill', 'stroke'] else elem.attrib[prop]

                # Ensure defaults for rendering
                if 'fill' not in new_attrs:
                    new_attrs['fill'] = 'none'
                if 'stroke' not in new_attrs:
                    new_attrs['stroke'] = 'black'
                if 'stroke-width' not in new_attrs:
                    new_attrs['stroke-width'] = '7'
                if 'stroke-linecap' not in new_attrs:
                    new_attrs['stroke-linecap'] = 'round'
                if 'stroke-linejoin' not in new_attrs:
                    new_attrs['stroke-linejoin'] = 'round'

                new_elem = ET.SubElement(new_root, tag, new_attrs)
                
        # Convert to string
        clean_xml = ET.tostring(new_root, encoding='utf-8').decode('utf-8')
        return clean_xml, (vb_w, vb_h)
    except Exception as e:
        print(f"Error sanitizing SVG {svg_path}: {e}")
        return None, None

def parse_derivations(derivation_text):
    # Parses a derivation text like: '(wings + wheel) - Character (superimposed)'
    # Returns a list of component terms in lowercase
    if not isinstance(derivation_text, str) or not derivation_text.strip():
        return []
    
    # Extract text in parentheses
    match = re.search(r'\(([^)]+)\)', derivation_text)
    if not match:
        return []
        
    inside = match.group(1)
    # Split by +
    components = [c.strip().lower() for c in inside.split('+')]
    
    # Strip modifier descriptions like ': carriage for a baby' or ' [modification...]'
    cleaned_components = []
    for comp in components:
        # Strip trailing colon comments
        comp = comp.split(':')[0].strip()
        # Strip bracket options
        comp = re.sub(r'\[[^\]]+\]', '', comp).strip()
        if comp:
            cleaned_components.append(comp)
            
    return cleaned_components

def determine_category(row, components):
    # Determines symbol category conforming to:
    # ["Base Spacing", "Indicator", "Punctuation", "Format Control", "Compound"]
    english = str(row.get('English', '')).lower()
    pos = str(row.get('POS', '')).lower()
    deriv = str(row.get('Derivation - explanation', '')).lower()
    
    if len(components) > 1 or 'combined' in deriv or 'superimposed' in deriv:
        return "Compound"
    if 'punctuation' in pos or 'punctuation' in deriv:
        return "Punctuation"
    if 'indicator' in english or 'indicator' in pos or 'indicator' in deriv:
        return "Indicator"
    if 'space' in english or 'format' in english:
        return "Format Control"
    return "Base Spacing"

def main():
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Setup schemas
    cursor.execute("DROP TABLE IF EXISTS symbols")
    cursor.execute("DROP TABLE IF EXISTS translations")
    cursor.execute("DROP TABLE IF EXISTS derivations")
    
    cursor.execute("""
    CREATE TABLE symbols (
        bci_id TEXT PRIMARY KEY,
        english_gloss TEXT,
        category TEXT,
        derivation_text TEXT,
        viewbox_w REAL,
        viewbox_h REAL,
        clean_svg TEXT
    )""")
    
    cursor.execute("""
    CREATE TABLE translations (
        bci_id TEXT,
        lang TEXT,
        gloss TEXT,
        FOREIGN KEY(bci_id) REFERENCES symbols(bci_id)
    )""")
    
    cursor.execute("""
    CREATE TABLE derivations (
        bci_id TEXT,
        component_term TEXT,
        FOREIGN KEY(bci_id) REFERENCES symbols(bci_id)
    )""")
    
    conn.commit()
    
    # Ingest BCI-AV spreadsheet
    excel_path = os.path.join(RAW_DIR, "BCI-AV_SKOG_2025-02-15_derivations_translations.xlsx")
    print(f"Loading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    # Track glossary mappings to resolve component terms back to numeric IDs
    # Map lowercase english terms to BCI-AV numeric ID
    gloss_to_id = {}
    for idx, row in df.iterrows():
        bci_id = str(row['BCI-AV#']).strip()
        eng = str(row.get('English', '')).strip()
        if eng:
            # English can contain comma-separated synonyms
            for term in eng.split(','):
                term_clean = term.strip().lower()
                if term_clean:
                    gloss_to_id[term_clean] = bci_id

    json_records = []
    print("Processing and sanitizing symbols...")
    
    for idx, row in df.iterrows():
        bci_id = str(row['BCI-AV#']).strip()
        english = str(row.get('English', '')).split(',')[0].strip() # use primary gloss
        deriv_text = str(row.get('Derivation - explanation', '')) if pd.notna(row.get('Derivation - explanation')) else ""
        
        # 1. Sanitize SVG
        svg_filename = f"{bci_id}.svg"
        svg_path = os.path.join(SVG_DIR, svg_filename)
        # Fallback to subfolder extracted from ZIP if needed
        if not os.path.exists(svg_path):
            svg_path = os.path.join(SVG_DIR, "bliss_svg_id", svg_filename)
            
        clean_svg, vb = sanitize_svg(svg_path)
        vb_w = vb[0] if vb else None
        vb_h = vb[1] if vb else None
        
        # 2. Parse derivations
        components = parse_derivations(deriv_text)
        
        # 3. Determine Category
        category = determine_category(row, components)
        
        # 4. Insert into symbols table
        cursor.execute("""
            INSERT INTO symbols (bci_id, english_gloss, category, derivation_text, viewbox_w, viewbox_h, clean_svg)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (bci_id, english, category, deriv_text, vb_w, vb_h, clean_svg))
        
        # 5. Insert translations
        glosses = {}
        for col_name, lang_code in LANGUAGES.items():
            val = row.get(col_name)
            if pd.notna(val):
                gloss_str = str(val).strip()
                cursor.execute("""
                    INSERT INTO translations (bci_id, lang, gloss)
                    VALUES (?, ?, ?)
                """, (bci_id, lang_code, gloss_str))
                # Store for JSON schema output
                if lang_code in ['en', 'sv', 'de', 'fr', 'nl']:
                    glosses[lang_code] = gloss_str

        # 6. Insert derivations
        for comp in components:
            cursor.execute("""
                INSERT INTO derivations (bci_id, component_term)
                VALUES (?, ?)
            """, (bci_id, comp))

        # 7. Extract raw SVG paths for unified JSON structure
        stroke_paths = []
        if clean_svg:
            try:
                elem_tree = ET.fromstring(clean_svg)
                for path_elem in elem_tree.iter():
                    tag = path_elem.tag.split('}')[-1]
                    # We can construct a path representing the SVG element
                    if tag == 'line':
                        x1 = path_elem.attrib.get('x1')
                        y1 = path_elem.attrib.get('y1')
                        x2 = path_elem.attrib.get('x2')
                        y2 = path_elem.attrib.get('y2')
                        stroke_paths.append(f"M {x1} {y1} L {x2} {y2}")
                    elif tag == 'path':
                        d = path_elem.attrib.get('d')
                        if d:
                            stroke_paths.append(d)
                    elif tag == 'circle':
                        cx = float(path_elem.attrib.get('cx', 0))
                        cy = float(path_elem.attrib.get('cy', 0))
                        r = float(path_elem.attrib.get('r', 0))
                        # Represent circle as two arcs
                        stroke_paths.append(f"M {cx-r} {cy} A {r} {r} 0 1 0 {cx+r} {cy} A {r} {r} 0 1 0 {cx-r} {cy}")
            except Exception as e:
                pass
                
        # Make sure mandatory schema properties are populated
        rec = {
            "bci_id": bci_id,
            "proposed_unicode": None,  # Will be populated in WP1.3
            "glosses": glosses,
            "derivations": components,
            "category": category,
            "geometry": {
                "stroke_paths": stroke_paths,
                "matrix_metrics": {
                    "skyline": 66.0,   # Default values matching metrics
                    "midline": 194.0,
                    "earthline": 258.0,
                    "base_width": vb_w if vb_w else 308.0
                }
            },
            "anchors": {
                "top_diacritic": {"x": (vb_w/2.0) if vb_w else 154.0, "y": 56.0},
                "bottom_diacritic": {"x": (vb_w/2.0) if vb_w else 154.0, "y": 268.0}
            },
            "input_method": {
                "primary_key": "",      # Will be populated from RIME mapping in WP3
                "subordinate_path": []
            }
        }
        json_records.append(rec)

    conn.commit()
    conn.close()
    
    # Save JSON mappings conforming to strict schema
    print(f"Saving JSON character records: {JSON_PATH}")
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(json_records, f, indent=2, ensure_ascii=False)
        
    print("ETL compilation completed successfully!")

if __name__ == "__main__":
    main()
