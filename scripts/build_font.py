#!/usr/bin/env python3
import os
import sqlite3
import json
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path
from fontTools.feaLib.builder import Builder

DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")

OUTPUT_OTF = os.path.join("data", "processed", "BlissFont-Regular.otf")
OUTPUT_WOFF2 = os.path.join("data", "processed", "BlissFont-Regular.woff2")
FEA_PATH = os.path.join("data", "processed", "features.fea")

def main():
    if not os.path.exists(JSON_PATH):
        print(f"Error: JSON data file not found at {JSON_PATH}")
        return
        
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)
        
    print(f"Loading {len(records)} Blissymbol records...")
    
    # 1. Initialize FontBuilder
    upm = 1000
    fb = FontBuilder(upm, isTTF=False)
    
    glyph_order = [".notdef", "space", "bracketleft", "bracketright"]
    cmap = {
        0x005B: "bracketleft",  # Standard Left Bracket '['
        0x005D: "bracketright"  # Standard Right Bracket ']'
    }
    cff_glyphs = {}
    metrics = {}
    
    # Define fallback .notdef
    pen = T2CharStringPen(500, glyphSet=None)
    pen.moveTo((50, 0))
    pen.lineTo((450, 0))
    pen.lineTo((450, 800))
    pen.lineTo((50, 800))
    pen.closePath()
    cff_glyphs[".notdef"] = pen.getCharString()
    metrics[".notdef"] = (500, 50)
    
    # Define space
    pen = T2CharStringPen(500, glyphSet=None)
    cff_glyphs["space"] = pen.getCharString()
    metrics["space"] = (500, 0)
    
    # Define bracketleft
    pen = T2CharStringPen(300, glyphSet=None)
    pen.moveTo((200, 850))
    pen.lineTo((100, 850))
    pen.lineTo((100, -150))
    pen.lineTo((200, -150))
    pen.lineTo((200, -100))
    pen.lineTo((150, -100))
    pen.lineTo((150, 800))
    pen.lineTo((200, 800))
    pen.closePath()
    cff_glyphs["bracketleft"] = pen.getCharString()
    metrics["bracketleft"] = (300, 50)

    # Define bracketright
    pen = T2CharStringPen(300, glyphSet=None)
    pen.moveTo((100, 850))
    pen.lineTo((200, 850))
    pen.lineTo((200, -150))
    pen.lineTo((100, -150))
    pen.lineTo((100, -100))
    pen.lineTo((150, -100))
    pen.lineTo((150, 800))
    pen.lineTo((100, 800))
    pen.closePath()
    cff_glyphs["bracketright"] = pen.getCharString()
    metrics["bracketright"] = (300, 50)
    
    # Track list of indicators and spacing base glyphs
    indicators = []
    base_glyphs = []
    
    print("Compiling glyph contours...")
    # 2. Iterate and build CFF charstrings
    for idx, r in enumerate(records):
        bci_id = r["bci_id"]
        glyph_name = f"glyph_{bci_id}"
        glyph_order.append(glyph_name)
        
        # Codepoint mapping
        p_uni = r.get("proposed_unicode")
        if p_uni and p_uni.startswith("U+"):
            try:
                cp = int(p_uni[2:], 16)
                cmap[cp] = glyph_name
            except ValueError:
                pass
                
        pua_cp = 0xE000 + idx
        cmap[pua_cp] = glyph_name
        
        # Dimensions and metrics scaling
        vb_w = r["geometry"]["matrix_metrics"]["base_width"]
        vb_h = 324.0 # default SVG height
        scale = upm / vb_h
        
        advance_width = int(vb_w * scale)
        pen = T2CharStringPen(advance_width, glyphSet=None)
        tpen = TransformPen(pen, (scale, 0, 0, -scale, 0, upm))
        
        # Parse SVG paths and draw onto pen
        for path_def in r["geometry"]["stroke_paths"]:
            try:
                parse_path(path_def, tpen)
            except Exception as e:
                pass # skip invalid path segments
                
        cff_glyphs[glyph_name] = pen.getCharString()
        metrics[glyph_name] = (advance_width, 0)
        
        # Classify for features
        if r.get("category") == "Indicator":
            indicators.append(glyph_name)
        else:
            base_glyphs.append(glyph_name)

    # Setup tables in FontBuilder
    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    
    fb.setupCFF(
        psName="BlissFont-Regular",
        fontInfo={"FullName": "BlissFont Regular", "FamilyName": "BlissFont"},
        charStringsDict=cff_glyphs,
        privateDict={"BlueValues": [-20, 0, 800, 820]}
    )
    
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader()
    fb.setupNameTable({"familyName": "BlissFont", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    
    # 3. Calculate bounds and compute diacritic anchors
    print("Calculating diacritic anchor coordinates from outline bounds...")
    glyph_set = fb.font.getGlyphSet()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(symbols)")
    cols = [col[1] for col in cursor.fetchall()]
    for col in ["anchor_top_x", "anchor_top_y", "anchor_bot_x", "anchor_bot_y"]:
        if col not in cols:
            cursor.execute(f"ALTER TABLE symbols ADD COLUMN {col} REAL")
    conn.commit()
    
    anchor_lookup = {}
    
    for r in records:
        bci_id = r["bci_id"]
        glyph_name = f"glyph_{bci_id}"
        
        if glyph_name in glyph_set:
            glyph = glyph_set[glyph_name]
            pen = BoundsPen(glyph_set)
            glyph.draw(pen)
            
            if pen.bounds:
                xMin, yMin, xMax, yMax = pen.bounds
                cx = (xMin + xMax) / 2.0
                
                # Dynamic variable offsets based on height class of glyph
                glyph_height = yMax - yMin
                if glyph_height < 300:
                    offset = 30
                elif glyph_height < 550:
                    offset = 45
                else:
                    offset = 60
                
                top_y = yMax + offset
                bot_y = yMin - offset
                
                anchor_lookup[glyph_name] = {
                    "top": (int(cx), int(top_y)),
                    "bot": (int(cx), int(bot_y))
                }
                
                cursor.execute("""
                    UPDATE symbols 
                    SET anchor_top_x = ?, anchor_top_y = ?, anchor_bot_x = ?, anchor_bot_y = ? 
                    WHERE bci_id = ?
                """, (cx, top_y, cx, bot_y, bci_id))
                
                r["anchors"]["top_diacritic"] = {"x": int(cx), "y": int(top_y)}
                r["anchors"]["bottom_diacritic"] = {"x": int(cx), "y": int(bot_y)}
            else:
                anchor_lookup[glyph_name] = {
                    "top": (500, 850),
                    "bot": (500, -50)
                }
                
    conn.commit()
    conn.close()
    
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print("Updated database and JSON files with variable GPOS coordinates.")
    
    # 4. Generate OpenType features FEA file
    print("Generating features.fea file...")
    fea_lines = []
    
    # Define classes
    fea_lines.append("# Glyph classes")
    fea_lines.append(f"@ALL_SYMBOLS = [{' '.join(base_glyphs)}];")
    
    # Define indicators mark class
    fea_lines.append("\n# Mark definitions")
    if indicators:
        fea_lines.append(f"markClass [{' '.join(indicators)}] <anchor 0 0> @INDICATORS;")
    else:
        fea_lines.append("markClass [space] <anchor 0 0> @INDICATORS;")
        
    fea_lines.append("\n# GPOS Anchors")
    fea_lines.append("feature mark {")
    fea_lines.append("    lookup mark2base {")
    
    for gname in base_glyphs:
        if gname in anchor_lookup:
            tx, ty = anchor_lookup[gname]["top"]
            fea_lines.append(f"        pos base {gname} <anchor {tx} {ty}> mark @INDICATORS;")
            
    fea_lines.append("    } mark2base;")
    fea_lines.append("} mark;")
    
    # Contextual Alternate Bracket Substitution for Combine Markers
    fea_lines.append("\n# Contextual Substitutions for Combine Markers")
    fea_lines.append("feature calt {")
    fea_lines.append("    # Substitute first combine_marker with left bracket")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    
    # Substitute second combine_marker with right bracket
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("} calt;")
    
    # Add RTL Mirroring GSUB feature
    fea_lines.append("\n# GSUB Mirroring for RTL Layouts")
    fea_lines.append("feature rtla {")
    fea_lines.append("    sub glyph_13902 by glyph_18224; # east -> west")
    fea_lines.append("    sub glyph_18224 by glyph_13902; # west -> east")
    fea_lines.append("    sub glyph_26211 by glyph_26212; # northeast -> northwest")
    fea_lines.append("    sub glyph_26212 by glyph_26211; # northwest -> northeast")
    fea_lines.append("    sub glyph_26245 by glyph_26246; # southeast -> southwest")
    fea_lines.append("    sub glyph_26246 by glyph_26245; # southwest -> southeast")
    fea_lines.append("    sub glyph_15187 by glyph_16673; # left -> right")
    fea_lines.append("    sub glyph_16673 by glyph_15187; # right -> left")
    fea_lines.append("    sub glyph_25577 by glyph_25604; # left_turn -> right_turn")
    fea_lines.append("    sub glyph_25604 by glyph_25577; # right_turn -> left_turn")
    fea_lines.append("} rtla;")
    
    with open(FEA_PATH, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fea_lines))
        
    # 5. Compile FEA and inject tables
    print("Compiling features and injecting GPOS/GSUB tables...")
    builder = Builder(fb.font, FEA_PATH)
    builder.build()
    
    # Save OTF
    fb.save(OUTPUT_OTF)
    print(f"OTF Font compiled successfully at: {OUTPUT_OTF}")
    
    # Save WOFF2
    font = TTFont(OUTPUT_OTF)
    font.flavor = "woff2"
    font.save(OUTPUT_WOFF2)
    print(f"WOFF2 Font compressed and saved at: {OUTPUT_WOFF2}")

if __name__ == "__main__":
    main()
