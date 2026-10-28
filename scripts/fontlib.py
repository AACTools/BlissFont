#!/usr/bin/env python3
"""
fontlib — shared glyph-geometry pipeline for the Bliss font compilers.

Used by build_font.py (BCI outline SVGs) and build_blissary_font.py
(Blissary stroke SVGs). Everything here is renderer-agnostic: SVG path
recordings -> shapely geometry -> fontTools pens, plus the helpers both
compilers share. Family-specific parts (cmap strategy, metrics, fea
generation) stay in the compiler scripts.
"""
from fontTools.pens.recordingPen import RecordingPen

import shapely
from shapely.geometry import LineString, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union


def evaluate_cubic_bezier(p0, p1, p2, p3, num_steps=12):
    points = []
    for step in range(1, num_steps + 1):
        t = step / float(num_steps)
        mt = 1.0 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def evaluate_quadratic_bezier(p0, p1, p2, num_steps=10):
    points = []
    for step in range(1, num_steps + 1):
        t = step / float(num_steps)
        mt = 1.0 - t
        x = mt**2 * p0[0] + 2 * mt * t * p1[0] + t**2 * p2[0]
        y = mt**2 * p0[1] + 2 * mt * t * p1[1] + t**2 * p2[1]
        points.append((x, y))
    return points


def recording_to_shapely_lines(recording):
    lines = []
    current_subpath = []
    cursor = (0, 0)

    for cmd, args in recording:
        if cmd == 'moveTo':
            if len(current_subpath) > 1:
                lines.append(LineString(current_subpath))
            cursor = args[0]
            current_subpath = [cursor]
        elif cmd == 'lineTo':
            cursor = args[0]
            current_subpath.append(cursor)
        elif cmd == 'curveTo':
            p1, p2, p3 = args
            pts = evaluate_cubic_bezier(cursor, p1, p2, p3)
            current_subpath.extend(pts)
            cursor = p3
        elif cmd == 'qCurveTo':
            if isinstance(args[0][0], (list, tuple)):
                pts = args[0]
            else:
                pts = args
            if len(pts) >= 2:
                prev = cursor
                for pt_idx in range(len(pts) - 1):
                    p1 = pts[pt_idx]
                    p2 = pts[pt_idx+1]
                    pts_eval = evaluate_quadratic_bezier(prev, p1, p2)
                    current_subpath.extend(pts_eval)
                    prev = p2
                cursor = pts[-1]
            elif len(pts) == 1:
                cursor = pts[0]
                current_subpath.append(cursor)
        elif cmd == 'closePath':
            if len(current_subpath) > 1:
                if current_subpath[-1] != current_subpath[0]:
                    current_subpath.append(current_subpath[0])
                lines.append(LineString(current_subpath))
            current_subpath = []

    if len(current_subpath) > 1:
        lines.append(LineString(current_subpath))

    return lines


def clean_coords(coords):
    cleaned = []
    for x, y in coords:
        rx, ry = int(round(x)), int(round(y))
        if not cleaned or (rx, ry) != cleaned[-1]:
            cleaned.append((rx, ry))
    if len(cleaned) >= 4:
        return cleaned
    return []


def draw_polygon_to_pen(poly, pen):
    oriented = orient(poly, sign=1.0)

    ext_coords = clean_coords(oriented.exterior.coords)
    if len(ext_coords) >= 4:
        pen.moveTo(ext_coords[0])
        for pt in ext_coords[1:-1]:
            pen.lineTo(pt)
        pen.closePath()

        for interior in oriented.interiors:
            int_coords = clean_coords(interior.coords)
            if len(int_coords) >= 4:
                pen.moveTo(int_coords[0])
                for pt in int_coords[1:-1]:
                    pen.lineTo(pt)
                pen.closePath()


def draw_geometry_to_pen(geom, pen):
    if geom.is_empty:
        return
    if geom.geom_type == 'Polygon':
        draw_polygon_to_pen(geom, pen)
    elif geom.geom_type == 'MultiPolygon':
        for poly in geom.geoms:
            draw_polygon_to_pen(poly, pen)
    elif geom.geom_type == 'GeometryCollection':
        for child in geom.geoms:
            draw_geometry_to_pen(child, pen)


def stroke_lines_to_geometry(lines, stroke_width):
    """Stroke each shapely line to a filled polygon (round caps/joins)."""
    polygons = []
    for line in lines:
        try:
            polygons.append(line.buffer(stroke_width / 2.0, cap_style='round', join_style='round'))
        except Exception:
            pass
    if polygons:
        return unary_union(polygons)
    return shapely.geometry.Polygon()


def paths_to_lines(stroke_paths, tpen):
    """Parse SVG path strings through a TransformPen -> shapely lines."""
    from fontTools.svgLib.path import parse_path
    rec_pen = RecordingPen()
    for path_def in stroke_paths:
        try:
            parse_path(path_def, tpen)
        except Exception:
            pass
    return recording_to_shapely_lines(rec_pen.value)
