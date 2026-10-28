#!/usr/bin/env python3
import os

import json
import re
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import TTFont
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.svgLib.path import parse_path
from fontTools.feaLib.builder import Builder

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.geometry.polygon import orient

from fontlib import (evaluate_cubic_bezier, evaluate_quadratic_bezier,
                       recording_to_shapely_lines, clean_coords,
                       draw_polygon_to_pen, draw_geometry_to_pen)

DB_PATH = os.path.join("data", "processed", "bliss_vocabulary.db")
JSON_PATH = os.path.join("data", "processed", "bliss_character_data.json")
BLISSARY_DIR = os.path.join("data", "raw", "blissary", "extracted")







def compile_blissary_weight(weight_name, stroke_val, weight_class, records):
    print(f"\n--- Compiling Blissary weight: {weight_name} (Stroke Width: {stroke_val}, Class: {weight_class}) ---")
    
    upm = 1000
    fb = FontBuilder(upm, isTTF=False)
    
    glyph_order = [".notdef", "space", "bracketleft", "bracketright"]
    cmap = {
        0x005B: "bracketleft",
        0x005D: "bracketright"
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
    
    indicators = []
    base_glyphs = []
    
    # Compile glyph contours
    for idx, r in enumerate(records):
        bci_id = r["bci_id"]
        glyph_name = f"glyph_{bci_id}"
        glyph_order.append(glyph_name)
        
        p_uni = r.get("proposed_unicode")
        if p_uni and p_uni.startswith("U+"):
            try:
                cp = int(p_uni[2:], 16)
                cmap[cp] = glyph_name
            except ValueError:
                pass
                
        # Legacy BMP PUA (backward compat). The block U+E000–U+F8FF has only
        # 6,400 slots; never map past it or we shadow CJK Compatibility.
        if idx < 6400:
            cmap[0xE000 + idx] = glyph_name
        
        # Stable Plane 15 PUA codepoint (0xF0000 + BCI ID)
        try:
            stable_cp = 0xF0000 + int(bci_id)
            cmap[stable_cp] = glyph_name
        except ValueError:
            pass
        
        # Check if Blissary SVG exists
        blissary_filename = f"{bci_id}.svg"
        blissary_path = os.path.join(BLISSARY_DIR, blissary_filename)
        
        rec_pen = RecordingPen()
        
        if os.path.exists(blissary_path):
            # 1. Parse Blissary SVG
            with open(blissary_path, "r", encoding="utf-8") as f_svg:
                svg_content = f_svg.read()
                
            # Extract paths
            svg_paths = re.findall(r'<path\s+d="([^"]+)"', svg_content)
            # Extract viewBox
            vb_match = re.search(r'viewBox="([^"]+)"', svg_content)
            if vb_match:
                vb_parts = list(map(float, vb_match.group(1).split()))
                xMin, yMin, xMax, yMax = vb_parts
            else:
                xMin, yMin, xMax, yMax = -0.75, -0.75, 9.5, 21.5
                
            # Compute Blissary specific metrics
            # Y goes from 16.0 (baseline) to 8.0 (sky line). Distance = 8.0 units.
            # In font UPM, this distance maps to 444.44 units (ascender=666.67, descender=222.22).
            scale = 444.44 / 8.0
            
            # Left padding is 50 units.
            # a=scale, b=0, c=0, d=-scale, dx=50 - scale*xMin, dy=222.22 + 16.0*scale
            tpen = TransformPen(rec_pen, (scale, 0, 0, -scale, 50.0 - scale * xMin, 16.0 * scale))
            
            for path_def in svg_paths:
                try:
                    parse_path(path_def, tpen)
                except Exception:
                    pass
            
            # Thicker stroke parameters for bold weights (relative to Blissary scale)
            # Blissary base stroke is 0.5. So we scale stroke_val directly.
            stroke_width = stroke_val * scale
            advance_width = int(round(100.0 + (xMax - xMin) * scale))
        else:
            # 2. Fallback to BCI SVG
            vb_w = r["geometry"]["matrix_metrics"]["base_width"]
            vb_h = 324.0
            scale = upm / vb_h
            
            tpen = TransformPen(rec_pen, (scale, 0, 0, -scale, 0, 252.0 * scale))
            for path_def in r["geometry"]["stroke_paths"]:
                try:
                    parse_path(path_def, tpen)
                except Exception:
                    pass
                    
            # For BCI fallback, we map stroke_val 0.5 to BCI stroke 7.0
            bci_stroke = (stroke_val / 0.5) * 7.0
            stroke_width = bci_stroke * scale
            advance_width = int(vb_w * scale)
            
        radius = stroke_width / 2.0
        lines = recording_to_shapely_lines(rec_pen.value)
        
        polygons = []
        for line in lines:
            try:
                poly = line.buffer(radius, cap_style='round', join_style='round')
                polygons.append(poly)
            except Exception:
                pass
                
        if polygons:
            union_geom = unary_union(polygons)
        else:
            union_geom = shapely.geometry.Polygon()
            
        pen = T2CharStringPen(advance_width, glyphSet=None)
        draw_geometry_to_pen(union_geom, pen)
                
        cff_glyphs[glyph_name] = pen.getCharString()
        metrics[glyph_name] = (advance_width, 0)
        
        gloss_lower = r.get("english_gloss", "").lower()
        is_indicator = (
            r.get("category") == "Indicator" or
            gloss_lower.startswith("indicator_") or
            gloss_lower == "plural"
        )
        if is_indicator:
            indicators.append(glyph_name)
        else:
            base_glyphs.append(glyph_name)

    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap)
    
    fb.setupCFF(
        psName=f"BlissaryFont-{weight_name}",
        fontInfo={"FullName": f"BlissaryFont {weight_name}", "FamilyName": "BlissaryFont"},
        charStringsDict=cff_glyphs,
        privateDict={"BlueValues": [-20, 0, 800, 820]}
    )
    
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=800, descent=-200, lineGap=0)
    fb.setupNameTable({
        "familyName": "BlissaryFont",
        "styleName": weight_name,
        "uniqueFontIdentifier": f"BlissaryFont {weight_name}; 1.000; 2026",
        "fullName": f"BlissaryFont {weight_name}",
        "psName": f"BlissaryFont-{weight_name}",
        "version": "Version 1.000"
    })
    fb.setupOS2(
        sTypoAscender=800,
        sTypoDescender=-200,
        sTypoLineGap=0,
        usWinAscent=800,
        usWinDescent=200,
        usWeightClass=weight_class
    )
    fb.setupPost()
    
    # Calculate GPOS anchors
    print("Calculating diacritic anchor coordinates...")
    glyph_set = fb.font.getGlyphSet()
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
                
                # Height class offset
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
            else:
                anchor_lookup[glyph_name] = {
                    "top": (500, 850),
                    "bot": (500, -50)
                }
                
    # Generate features FEA
    fea_lines = []
    fea_lines.append("# Glyph classes")
    fea_lines.append(f"@ALL_SYMBOLS = [{' '.join(base_glyphs)}];")
    
    fea_lines.append("\n# Mark definitions")
    if indicators:
        for ind_name in indicators:
            if ind_name in glyph_set:
                glyph = glyph_set[ind_name]
                pen = BoundsPen(glyph_set)
                glyph.draw(pen)
                if pen.bounds:
                    xMin, yMin, xMax, yMax = pen.bounds
                    cx = (xMin + xMax) / 2.0
                    cy = yMin
                    fea_lines.append(f"markClass {ind_name} <anchor {int(round(cx))} {int(round(cy))}> @INDICATORS;")
                else:
                    fea_lines.append(f"markClass {ind_name} <anchor 250 850> @INDICATORS;")
            else:
                fea_lines.append(f"markClass {ind_name} <anchor 250 850> @INDICATORS;")
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
    
    # Combine marker GSUB
    fea_lines.append("\n# Contextual Substitutions for Combine Markers")
    fea_lines.append("feature calt {")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub glyph_13382' @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382 by bracketleft;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("    sub bracketleft @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS @ALL_SYMBOLS glyph_13382' by bracketright;")
    fea_lines.append("} calt;")
    
    # RTL Mirroring
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
    
    temp_fea = os.path.join("data", "processed", f"temp_blissary_{weight_name}.fea")
    with open(temp_fea, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fea_lines))
        
    builder = Builder(fb.font, temp_fea)
    builder.build()
    
    # Save OTF
    out_otf = os.path.join("data", "processed", f"BlissaryFont-{weight_name}.otf")
    fb.save(out_otf)
    print(f"OTF Font ({weight_name}) compiled successfully at: {out_otf}")
    
    # Save WOFF2
    out_woff2 = os.path.join("data", "processed", f"BlissaryFont-{weight_name}.woff2")
    font = TTFont(out_otf)
    font.flavor = "woff2"
    font.save(out_woff2)
    print(f"WOFF2 Font ({weight_name}) compiled successfully at: {out_woff2}")
    
    if os.path.exists(temp_fea):
        os.remove(temp_fea)

def main():
    if not os.path.exists(JSON_PATH):
        print(f"Error: JSON data file not found at {JSON_PATH}")
        return
        
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        records = json.load(f)
        
    # Define Blissary weights
    # Default Blissary stroke is 0.5.
    weights = [
        {"name": "Regular", "stroke": 0.5, "class": 400},
        {"name": "SemiBold", "stroke": 0.75, "class": 600},
        {"name": "Bold", "stroke": 1.0, "class": 700}
    ]
    
    for w in weights:
        compile_blissary_weight(w["name"], w["stroke"], w["class"], records)
        
    print("\nAll Blissary weights compiled successfully!")

if __name__ == "__main__":
    main()
