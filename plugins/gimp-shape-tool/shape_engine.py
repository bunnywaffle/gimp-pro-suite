#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
==============================================================================
Mathematical Shape Generation Engine for GIMP 3.2 Vector Shape Tool
==============================================================================
Pure Python mathematical generators producing precise SVG path data ('d' attribute).
Supports Primitives, Polygons, Stars, Arrows, Speech Bubbles, Natural Clouds,
Organic Blobs, Badges, Spirals, Gears, and Symbols with zero overlapping cutout bugs.
"""

import math
from typing import List, Tuple, Optional

K_BEZIER = 0.5522847498307933984022516322796

def clamp(val: float, min_v: float, max_v: float) -> float:
    return max(min_v, min(val, max_v))

def format_num(val: float) -> str:
    return f"{round(val, 3):g}"

def build_svg_document(path_d: str, width: float, height: float) -> str:
    w_str = format_num(width)
    h_str = format_num(height)
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
        f'width="{w_str}" height="{h_str}" viewBox="0 0 {w_str} {h_str}">\n'
        f'  <path d="{path_d}" />\n'
        f'</svg>'
    )

def rotate_point(px: float, py: float, cx: float, cy: float, angle_rad: float) -> Tuple[float, float]:
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    dx = px - cx
    dy = py - cy
    return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)

# ----------------------------------------------------------------------------
# 1. BASIC PRIMITIVES
# ----------------------------------------------------------------------------
def generate_rectangle(x: float, y: float, w: float, h: float,
                       r_tl: float = 0.0, r_tr: float = 0.0,
                       r_br: float = 0.0, r_bl: float = 0.0,
                       corner_style: str = "round") -> str:
    max_r = min(w, h) / 2.0
    r_tl = clamp(r_tl, 0.0, max_r)
    r_tr = clamp(r_tr, 0.0, max_r)
    r_br = clamp(r_br, 0.0, max_r)
    r_bl = clamp(r_bl, 0.0, max_r)

    if r_tl == 0 and r_tr == 0 and r_br == 0 and r_bl == 0:
        return f"M {format_num(x)} {format_num(y)} H {format_num(x + w)} V {format_num(y + h)} H {format_num(x)} Z"

    d = [f"M {format_num(x + r_tl)} {format_num(y)}"]
    d.append(f"H {format_num(x + w - r_tr)}")

    # Top-Right
    if r_tr > 0:
        if corner_style == "round":
            k = K_BEZIER * r_tr
            d.append(f"C {format_num(x + w - r_tr + k)} {format_num(y)} {format_num(x + w)} {format_num(y + r_tr - k)} {format_num(x + w)} {format_num(y + r_tr)}")
        elif corner_style == "chamfer":
            d.append(f"L {format_num(x + w)} {format_num(y + r_tr)}")
        elif corner_style == "inverted":
            d.append(f"A {format_num(r_tr)} {format_num(r_tr)} 0 0 0 {format_num(x + w)} {format_num(y + r_tr)}")
    d.append(f"V {format_num(y + h - r_br)}")

    # Bottom-Right
    if r_br > 0:
        if corner_style == "round":
            k = K_BEZIER * r_br
            d.append(f"C {format_num(x + w)} {format_num(y + h - r_br + k)} {format_num(x + w - r_br + k)} {format_num(y + h)} {format_num(x + w - r_br)} {format_num(y + h)}")
        elif corner_style == "chamfer":
            d.append(f"L {format_num(x + w - r_br)} {format_num(y + h)}")
        elif corner_style == "inverted":
            d.append(f"A {format_num(r_br)} {format_num(r_br)} 0 0 0 {format_num(x + w - r_br)} {format_num(y + h)}")
    d.append(f"H {format_num(x + r_bl)}")

    # Bottom-Left
    if r_bl > 0:
        if corner_style == "round":
            k = K_BEZIER * r_bl
            d.append(f"C {format_num(x + r_bl - k)} {format_num(y + h)} {format_num(x)} {format_num(y + h - r_bl + k)} {format_num(x)} {format_num(y + h - r_bl)}")
        elif corner_style == "chamfer":
            d.append(f"L {format_num(x)} {format_num(y + h - r_bl)}")
        elif corner_style == "inverted":
            d.append(f"A {format_num(r_bl)} {format_num(r_bl)} 0 0 0 {format_num(x)} {format_num(y + h - r_bl)}")
    d.append(f"V {format_num(y + r_tl)}")

    # Top-Left
    if r_tl > 0:
        if corner_style == "round":
            k = K_BEZIER * r_tl
            d.append(f"C {format_num(x)} {format_num(y + r_tl - k)} {format_num(x + r_tl - k)} {format_num(y)} {format_num(x + r_tl)} {format_num(y)}")
        elif corner_style == "chamfer":
            d.append(f"L {format_num(x + r_tl)} {format_num(y)}")
        elif corner_style == "inverted":
            d.append(f"A {format_num(r_tl)} {format_num(r_tl)} 0 0 0 {format_num(x + r_tl)} {format_num(y)}")

    d.append("Z")
    return " ".join(d)

def generate_ellipse(cx: float, cy: float, rx: float, ry: float,
                     start_angle_deg: float = 0.0, end_angle_deg: float = 360.0,
                     mode: str = "full", inner_ratio: float = 0.0) -> str:
    sweep = (end_angle_deg - start_angle_deg) % 360.0
    if sweep == 0 and end_angle_deg > start_angle_deg:
        sweep = 360.0

    if sweep >= 360.0 and inner_ratio <= 0.0:
        kx = K_BEZIER * rx
        ky = K_BEZIER * ry
        return (
            f"M {format_num(cx - rx)} {format_num(cy)} "
            f"C {format_num(cx - rx)} {format_num(cy - ky)} {format_num(cx - kx)} {format_num(cy - ry)} {format_num(cx)} {format_num(cy - ry)} "
            f"C {format_num(cx + kx)} {format_num(cy - ry)} {format_num(cx + rx)} {format_num(cy - ky)} {format_num(cx + rx)} {format_num(cy)} "
            f"C {format_num(cx + rx)} {format_num(cy + ky)} {format_num(cx + kx)} {format_num(cy + ry)} {format_num(cx)} {format_num(cy + ry)} "
            f"C {format_num(cx - kx)} {format_num(cy + ry)} {format_num(cx - rx)} {format_num(cy + ky)} {format_num(cx - rx)} {format_num(cy)} Z"
        )
    elif sweep >= 360.0 and inner_ratio > 0.0:
        r_in_x = rx * clamp(inner_ratio, 0.05, 0.95)
        r_in_y = ry * clamp(inner_ratio, 0.05, 0.95)
        kx_out = K_BEZIER * rx
        ky_out = K_BEZIER * ry
        kx_in = K_BEZIER * r_in_x
        ky_in = K_BEZIER * r_in_y
        outer_path = (
            f"M {format_num(cx - rx)} {format_num(cy)} "
            f"C {format_num(cx - rx)} {format_num(cy - ky_out)} {format_num(cx - kx_out)} {format_num(cy - ry)} {format_num(cx)} {format_num(cy - ry)} "
            f"C {format_num(cx + kx_out)} {format_num(cy - ry)} {format_num(cx + rx)} {format_num(cy - ky_out)} {format_num(cx + rx)} {format_num(cy)} "
            f"C {format_num(cx + rx)} {format_num(cy + ky_out)} {format_num(cx + kx_out)} {format_num(cy + ry)} {format_num(cx)} {format_num(cy + ry)} "
            f"C {format_num(cx - kx_out)} {format_num(cy + ry)} {format_num(cx - rx)} {format_num(cy + ky_out)} {format_num(cx - rx)} {format_num(cy)} Z"
        )
        inner_path = (
            f" M {format_num(cx - r_in_x)} {format_num(cy)} "
            f"C {format_num(cx - r_in_x)} {format_num(cy + ky_in)} {format_num(cx - kx_in)} {format_num(cy + r_in_y)} {format_num(cx)} {format_num(cy + r_in_y)} "
            f"C {format_num(cx + kx_in)} {format_num(cy + r_in_y)} {format_num(cx + r_in_x)} {format_num(cy + ky_in)} {format_num(cx + r_in_x)} {format_num(cy)} "
            f"C {format_num(cx + r_in_x)} {format_num(cy - ky_in)} {format_num(cx + kx_in)} {format_num(cy - r_in_y)} {format_num(cx)} {format_num(cy - r_in_y)} "
            f"C {format_num(cx - kx_in)} {format_num(cy - r_in_y)} {format_num(cx - r_in_x)} {format_num(cy - ky_in)} {format_num(cx - r_in_x)} {format_num(cy)} Z"
        )
        return outer_path + inner_path

    a1 = math.radians(start_angle_deg)
    a2 = math.radians(start_angle_deg + sweep)
    p1 = (cx + rx * math.cos(a1), cy + ry * math.sin(a1))
    p2 = (cx + rx * math.cos(a2), cy + ry * math.sin(a2))
    large_arc = 1 if sweep > 180.0 else 0

    if mode == "arc":
        return f"M {format_num(p1[0])} {format_num(p1[1])} A {format_num(rx)} {format_num(ry)} 0 {large_arc} 1 {format_num(p2[0])} {format_num(p2[1])}"
    elif mode == "pie":
        return f"M {format_num(cx)} {format_num(cy)} L {format_num(p1[0])} {format_num(p1[1])} A {format_num(rx)} {format_num(ry)} 0 {large_arc} 1 {format_num(p2[0])} {format_num(p2[1])} Z"
    elif mode == "annular":
        r_in_x = rx * clamp(inner_ratio, 0.05, 0.95)
        r_in_y = ry * clamp(inner_ratio, 0.05, 0.95)
        p1_in = (cx + r_in_x * math.cos(a1), cy + r_in_y * math.sin(a1))
        p2_in = (cx + r_in_x * math.cos(a2), cy + r_in_y * math.sin(a2))
        return (
            f"M {format_num(p1_in[0])} {format_num(p1_in[1])} "
            f"L {format_num(p1[0])} {format_num(p1[1])} "
            f"A {format_num(rx)} {format_num(ry)} 0 {large_arc} 1 {format_num(p2[0])} {format_num(p2[1])} "
            f"L {format_num(p2_in[0])} {format_num(p2_in[1])} "
            f"A {format_num(r_in_x)} {format_num(r_in_y)} 0 {large_arc} 0 {format_num(p1_in[0])} {format_num(p1_in[1])} Z"
        )
    return ""

def generate_polygon_with_fillets(points: List[Tuple[float, float]], corner_radius: float = 0.0) -> str:
    n = len(points)
    if n < 3:
        return ""
    if corner_radius <= 0.0:
        d = [f"M {format_num(points[0][0])} {format_num(points[0][1])}"]
        for p in points[1:]:
            d.append(f"L {format_num(p[0])} {format_num(p[1])}")
        d.append("Z")
        return " ".join(d)

    d = []
    for i in range(n):
        p_prev = points[(i - 1 + n) % n]
        p_curr = points[i]
        p_next = points[(i + 1) % n]

        v1 = (p_prev[0] - p_curr[0], p_prev[1] - p_curr[1])
        v2 = (p_next[0] - p_curr[0], p_next[1] - p_curr[1])
        len1 = math.hypot(v1[0], v1[1])
        len2 = math.hypot(v2[0], v2[1])
        if len1 < 1e-4 or len2 < 1e-4:
            continue

        u1 = (v1[0] / len1, v1[1] / len1)
        u2 = (v2[0] / len2, v2[1] / len2)
        dot = clamp(u1[0] * u2[0] + u1[1] * u2[1], -1.0, 1.0)
        angle = math.acos(dot)
        half_angle = angle / 2.0
        if half_angle < 1e-3 or math.sin(half_angle) < 1e-3:
            continue

        max_tangent_dist = min(len1, len2) / 2.0
        tangent_dist = min(corner_radius / math.tan(half_angle), max_tangent_dist)

        start_pt = (p_curr[0] + u1[0] * tangent_dist, p_curr[1] + u1[1] * tangent_dist)
        end_pt = (p_curr[0] + u2[0] * tangent_dist, p_curr[1] + u2[1] * tangent_dist)

        if i == 0:
            d.append(f"M {format_num(start_pt[0])} {format_num(start_pt[1])}")
        else:
            d.append(f"L {format_num(start_pt[0])} {format_num(start_pt[1])}")

        d.append(f"Q {format_num(p_curr[0])} {format_num(p_curr[1])} {format_num(end_pt[0])} {format_num(end_pt[1])}")

    d.append("Z")
    return " ".join(d)

def generate_triangle(cx: float, cy: float, w: float, h: float,
                      preset: str = "equilateral", corner_radius: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    bx = cx - half_w
    by = cy - half_h

    if preset == "equilateral":
        pts = [(cx, by), (bx + w, by + h), (bx, by + h)]
    elif preset == "isosceles":
        pts = [(cx, by), (bx + w, by + h), (bx, by + h)]
    elif preset == "right_bl":
        pts = [(bx, by), (bx + w, by + h), (bx, by + h)]
    elif preset == "right_br":
        pts = [(bx + w, by), (bx + w, by + h), (bx, by + h)]
    elif preset == "right_tl":
        pts = [(bx, by), (bx + w, by), (bx, by + h)]
    elif preset == "right_tr":
        pts = [(bx, by), (bx + w, by), (bx + w, by + h)]
    else:
        pts = [(cx, by), (bx + w, by + h), (bx, by + h)]

    return generate_polygon_with_fillets(pts, corner_radius)

# ----------------------------------------------------------------------------
# 2. POLYGONS & STARS
# ----------------------------------------------------------------------------
def generate_regular_polygon(cx: float, cy: float, rx: float, ry: float,
                             sides: int = 5, rotation_deg: float = 0.0,
                             corner_radius: float = 0.0) -> str:
    sides = max(3, min(sides, 64))
    rot_rad = math.radians(rotation_deg - 90.0)
    pts = []
    for i in range(sides):
        angle = rot_rad + 2.0 * math.pi * i / sides
        pts.append((cx + rx * math.cos(angle), cy + ry * math.sin(angle)))
    return generate_polygon_with_fillets(pts, corner_radius)

def generate_star(cx: float, cy: float, rx: float, ry: float,
                  inner_ratio: float = 0.5, points: int = 5,
                  rotation_deg: float = 0.0, starburst_mode: str = "standard",
                  corner_radius: float = 0.0) -> str:
    points = max(3, min(points, 32))
    total_vertices = points * 2
    rot_rad = math.radians(rotation_deg - 90.0)
    pts = []

    for i in range(total_vertices):
        angle = rot_rad + math.pi * i / points
        if i % 2 == 0:
            if starburst_mode == "burst_multi" and (i // 2) % 2 == 1:
                r_x = rx * 0.85
                r_y = ry * 0.85
            else:
                r_x = rx
                r_y = ry
        else:
            r_x = rx * inner_ratio
            r_y = ry * inner_ratio
        pts.append((cx + r_x * math.cos(angle), cy + r_y * math.sin(angle)))

    return generate_polygon_with_fillets(pts, corner_radius)

def generate_parallelogram(cx: float, cy: float, w: float, h: float,
                           skew_deg: float = 20.0, corner_radius: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    skew_px = half_h * math.tan(math.radians(clamp(skew_deg, -60.0, 60.0)))
    pts = [
        (cx - half_w + skew_px, cy - half_h),
        (cx + half_w + skew_px, cy - half_h),
        (cx + half_w - skew_px, cy + half_h),
        (cx - half_w - skew_px, cy + half_h),
    ]
    return generate_polygon_with_fillets(pts, corner_radius)

def generate_trapezoid(cx: float, cy: float, w: float, h: float,
                       top_ratio: float = 0.6, corner_radius: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    top_half_w = half_w * clamp(top_ratio, 0.1, 1.0)
    pts = [
        (cx - top_half_w, cy - half_h),
        (cx + top_half_w, cy - half_h),
        (cx + half_w, cy + half_h),
        (cx - half_w, cy + half_h),
    ]
    return generate_polygon_with_fillets(pts, corner_radius)

def generate_rhombus(cx: float, cy: float, w: float, h: float,
                     corner_radius: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    pts = [
        (cx, cy - half_h),
        (cx + half_w, cy),
        (cx, cy + half_h),
        (cx - half_w, cy)
    ]
    return generate_polygon_with_fillets(pts, corner_radius)

def generate_hexagon_octagon(cx: float, cy: float, rx: float, ry: float,
                             sides: int = 6, pointy_top: bool = False,
                             corner_radius: float = 0.0) -> str:
    rot = 30.0 if (sides == 6 and pointy_top) else (22.5 if (sides == 8 and pointy_top) else 0.0)
    return generate_regular_polygon(cx, cy, rx, ry, sides=sides, rotation_deg=rot, corner_radius=corner_radius)

# ----------------------------------------------------------------------------
# 3. UI & DIAGRAMMING (ARROWS, SPEECH BUBBLES, NATURAL CLOUDS, ORGANIC BLOBS)
# ----------------------------------------------------------------------------
def generate_arrow(cx: float, cy: float, w: float, h: float,
                   arrow_type: str = "linear", shaft_ratio: float = 0.4,
                   head_len_ratio: float = 0.4, double_headed: bool = False,
                   rotation_deg: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    shaft_half_h = half_h * clamp(shaft_ratio, 0.1, 0.8)
    head_len = w * clamp(head_len_ratio, 0.15, 0.6)

    if arrow_type == "chevron":
        pts = [
            (cx - half_w, cy - half_h),
            (cx + half_w - head_len, cy - half_h),
            (cx + half_w, cy),
            (cx + half_w - head_len, cy + half_h),
            (cx - half_w, cy + half_h),
            (cx - half_w + head_len, cy),
        ]
    elif double_headed:
        pts = [
            (cx + half_w - head_len, cy - half_h),
            (cx + half_w, cy),
            (cx + half_w - head_len, cy + half_h),
            (cx + half_w - head_len, cy + shaft_half_h),
            (cx - half_w + head_len, cy + shaft_half_h),
            (cx - half_w + head_len, cy + half_h),
            (cx - half_w, cy),
            (cx - half_w + head_len, cy - half_h),
            (cx - half_w + head_len, cy - shaft_half_h),
            (cx + half_w - head_len, cy - shaft_half_h),
        ]
    elif arrow_type == "curved":
        r_out = w * 0.9
        r_in = r_out - h * shaft_ratio
        h_len = h * head_len_ratio * 1.5
        head_out = r_out + h * 0.2
        head_in = r_in - h * 0.2
        bx = cx - half_w
        by = cy + half_h
        return (
            f"M {format_num(bx)} {format_num(by - r_in)} "
            f"A {format_num(r_in)} {format_num(r_in)} 0 0 1 {format_num(bx + r_in - h_len)} {format_num(by)} "
            f"L {format_num(bx + r_in - h_len)} {format_num(by + (head_out - r_out))} "
            f"L {format_num(bx + (r_in + r_out) / 2.0)} {format_num(by + h_len * 0.8)} "
            f"L {format_num(bx + r_out + h_len)} {format_num(by - (r_out - head_in))} "
            f"L {format_num(bx + r_out)} {format_num(by - (r_out - head_in))} "
            f"A {format_num(r_out)} {format_num(r_out)} 0 0 0 {format_num(bx)} {format_num(by - r_out)} Z"
        )
    else: # linear
        pts = [
            (cx - half_w, cy - shaft_half_h),
            (cx + half_w - head_len, cy - shaft_half_h),
            (cx + half_w - head_len, cy - half_h),
            (cx + half_w, cy),
            (cx + half_w - head_len, cy + half_h),
            (cx + half_w - head_len, cy + shaft_half_h),
            (cx - half_w, cy + shaft_half_h),
        ]

    if rotation_deg != 0.0:
        rot_rad = math.radians(rotation_deg)
        pts = [rotate_point(p[0], p[1], cx, cy, rot_rad) for p in pts]

    return generate_polygon_with_fillets(pts, corner_radius=0.0)

def generate_speech_bubble(cx: float, cy: float, w: float, h: float,
                           bubble_type: str = "rounded",
                           corner_radius: float = 18.0,
                           tail_pos: str = "bottom_left",
                           tail_length: float = 0.35,
                           tail_width: float = 0.25,
                           **kwargs) -> str:
    """
    Generates an authentic comic / UI speech bubble with an outward-extending tail.
    """
    half_w = w / 2.0
    half_h = h / 2.0
    bx = cx - half_w
    by = cy - half_h
    t_len = clamp(tail_length, 0.15, 0.8) * h
    t_base = clamp(tail_width, 0.1, 0.45) * w

    if bubble_type == "thought_cloud":
        # Fluffy thought cloud with cleanly separated non-overlapping thought bubbles
        body_w = w * 0.90
        body_h = h * 0.75
        body_cx = cx
        body_cy = cy - h * 0.10
        body_bx = body_cx - body_w / 2.0
        body_by = body_cy - body_h / 2.0

        # Organic 6-puff cloud outline
        body_d = [
            f"M {format_num(body_bx + body_w * 0.18)} {format_num(body_by + body_h * 0.78)}",
            f"C {format_num(body_bx - body_w * 0.06)} {format_num(body_by + body_h * 0.75)} {format_num(body_bx - body_w * 0.05)} {format_num(body_by + body_h * 0.40)} {format_num(body_bx + body_w * 0.14)} {format_num(body_by + body_h * 0.38)}",
            f"C {format_num(body_bx + body_w * 0.12)} {format_num(body_by + body_h * 0.08)} {format_num(body_bx + body_w * 0.38)} {format_num(body_by + body_h * 0.06)} {format_num(body_bx + body_w * 0.48)} {format_num(body_by + body_h * 0.24)}",
            f"C {format_num(body_bx + body_w * 0.55)} {format_num(body_by - body_h * 0.04)} {format_num(body_bx + body_w * 0.88)} {format_num(body_by + body_h * 0.04)} {format_num(body_bx + body_w * 0.88)} {format_num(body_by + body_h * 0.36)}",
            f"C {format_num(body_bx + body_w * 1.06)} {format_num(body_by + body_h * 0.42)} {format_num(body_bx + body_w * 1.05)} {format_num(body_by + body_h * 0.75)} {format_num(body_bx + body_w * 0.82)} {format_num(body_by + body_h * 0.78)}",
            f"C {format_num(body_bx + body_w * 0.75)} {format_num(body_by + body_h * 1.04)} {format_num(body_bx + body_w * 0.25)} {format_num(body_by + body_h * 1.04)} {format_num(body_bx + body_w * 0.18)} {format_num(body_by + body_h * 0.78)}",
            "Z"
        ]
        
        dir_map = {
            "bottom_left": (-w * 0.36, h * 0.38, -w * 0.46, h * 0.48),
            "bottom_center": (0.0, h * 0.38, 0.0, h * 0.49),
            "bottom_right": (w * 0.36, h * 0.38, w * 0.46, h * 0.48),
            "top_left": (-w * 0.36, -h * 0.38, -w * 0.46, -h * 0.48),
            "top_right": (w * 0.36, -h * 0.38, w * 0.46, -h * 0.48),
            "left": (-w * 0.46, h * 0.18, -w * 0.56, h * 0.28),
            "right": (w * 0.46, h * 0.18, w * 0.56, h * 0.28),
        }
        dx1, dy1, dx2, dy2 = dir_map.get(tail_pos, (-w * 0.36, h * 0.38, -w * 0.46, h * 0.48))
        
        b1_x = cx + dx1
        b1_y = cy + dy1
        r1 = min(w, h) * 0.075
        
        b2_x = cx + dx2
        b2_y = cy + dy2
        r2 = min(w, h) * 0.04
        
        c1 = f"M {format_num(b1_x + r1)} {format_num(b1_y)} A {format_num(r1)} {format_num(r1)} 0 1 0 {format_num(b1_x - r1)} {format_num(b1_y)} A {format_num(r1)} {format_num(r1)} 0 1 0 {format_num(b1_x + r1)} {format_num(b1_y)} Z"
        c2 = f"M {format_num(b2_x + r2)} {format_num(b2_y)} A {format_num(r2)} {format_num(r2)} 0 1 0 {format_num(b2_x - r2)} {format_num(b2_y)} A {format_num(r2)} {format_num(r2)} 0 1 0 {format_num(b2_x + r2)} {format_num(b2_y)} Z"
        return f"{' '.join(body_d)} {c1} {c2}"

    elif bubble_type == "oval":
        rx = half_w
        ry = half_h
        ang_map = {
            "bottom_left": math.radians(125),
            "bottom_center": math.radians(90),
            "bottom_right": math.radians(55),
            "top_left": math.radians(235),
            "top_right": math.radians(305),
            "left": math.radians(160),
            "right": math.radians(20)
        }
        tail_ang = ang_map.get(tail_pos, math.radians(115))
        base_half_ang = math.radians(15)
        
        a1 = tail_ang - base_half_ang
        a2 = tail_ang + base_half_ang
        
        p1 = (cx + rx * math.cos(a1), cy + ry * math.sin(a1))
        p2 = (cx + rx * math.cos(a2), cy + ry * math.sin(a2))
        
        tip_x = cx + (rx + t_len) * math.cos(tail_ang)
        tip_y = cy + (ry + t_len) * math.sin(tail_ang)
        
        d = [
            f"M {format_num(p1[0])} {format_num(p1[1])}",
            f"L {format_num(tip_x)} {format_num(tip_y)}",
            f"L {format_num(p2[0])} {format_num(p2[1])}",
            f"A {format_num(rx)} {format_num(ry)} 0 1 0 {format_num(p1[0])} {format_num(p1[1])}",
            "Z"
        ]
        return " ".join(d)

    else:
        r = 0.0 if bubble_type == "rect" else clamp(corner_radius, 4.0, min(half_w, half_h) * 0.4)
        k = K_BEZIER * r
        d = []
        d.append(f"M {format_num(bx + r)} {format_num(by)}")
        
        if tail_pos == "top_left":
            d.append(f"L {format_num(bx + w * 0.2)} {format_num(by)}")
            d.append(f"L {format_num(bx + w * 0.1 - t_len * 0.3)} {format_num(by - t_len)}")
            d.append(f"L {format_num(bx + w * 0.2 + t_base)} {format_num(by)}")
        elif tail_pos == "top_right":
            d.append(f"L {format_num(bx + w * 0.8 - t_base)} {format_num(by)}")
            d.append(f"L {format_num(bx + w * 0.9 + t_len * 0.3)} {format_num(by - t_len)}")
            d.append(f"L {format_num(bx + w * 0.8)} {format_num(by)}")
        d.append(f"L {format_num(bx + w - r)} {format_num(by)}")
        
        if r > 0:
            d.append(f"C {format_num(bx + w - r + k)} {format_num(by)} {format_num(bx + w)} {format_num(by + r - k)} {format_num(bx + w)} {format_num(by + r)}")
        
        if tail_pos == "right":
            d.append(f"L {format_num(bx + w)} {format_num(cy - t_base / 2.0)}")
            d.append(f"L {format_num(bx + w + t_len)} {format_num(cy + t_len * 0.3)}")
            d.append(f"L {format_num(bx + w)} {format_num(cy + t_base / 2.0)}")
        d.append(f"L {format_num(bx + w)} {format_num(by + h - r)}")
        
        if r > 0:
            d.append(f"C {format_num(bx + w)} {format_num(by + h - r + k)} {format_num(bx + w - r + k)} {format_num(by + h)} {format_num(bx + w - r)} {format_num(by + h)}")
        
        if tail_pos == "bottom_right":
            d.append(f"L {format_num(bx + w * 0.8)} {format_num(by + h)}")
            d.append(f"L {format_num(bx + w * 0.85 + t_len * 0.3)} {format_num(by + h + t_len)}")
            d.append(f"L {format_num(bx + w * 0.8 - t_base)} {format_num(by + h)}")
        elif tail_pos == "bottom_center":
            d.append(f"L {format_num(cx + t_base / 2.0)} {format_num(by + h)}")
            d.append(f"L {format_num(cx - t_len * 0.2)} {format_num(by + h + t_len)}")
            d.append(f"L {format_num(cx - t_base / 2.0)} {format_num(by + h)}")
        elif tail_pos == "bottom_left":
            d.append(f"L {format_num(bx + w * 0.2 + t_base)} {format_num(by + h)}")
            d.append(f"L {format_num(bx + w * 0.15 - t_len * 0.3)} {format_num(by + h + t_len)}")
            d.append(f"L {format_num(bx + w * 0.2)} {format_num(by + h)}")
        d.append(f"L {format_num(bx + r)} {format_num(by + h)}")
        
        if r > 0:
            d.append(f"C {format_num(bx + r - k)} {format_num(by + h)} {format_num(bx)} {format_num(by + h - r + k)} {format_num(bx)} {format_num(by + h - r)}")
        
        if tail_pos == "left":
            d.append(f"L {format_num(bx)} {format_num(cy + t_base / 2.0)}")
            d.append(f"L {format_num(bx - t_len)} {format_num(cy + t_len * 0.3)}")
            d.append(f"L {format_num(bx)} {format_num(cy - t_base / 2.0)}")
        d.append(f"L {format_num(bx)} {format_num(by + r)}")
        
        if r > 0:
            d.append(f"C {format_num(bx)} {format_num(by + r - k)} {format_num(bx + r - k)} {format_num(by)} {format_num(bx + r)} {format_num(by)}")
        
        d.append("Z")
        return " ".join(d)

# ----------------------------------------------------------------------------
# 4. NATURAL CLOUD GENERATORS
# ----------------------------------------------------------------------------
def generate_cloud(cx: float, cy: float, w: float, h: float,
                   cloud_type: str = "cumulus", puffs: int = 5) -> str:
    """
    Generates natural cartoon clouds with asymmetric organic lobes.
    cloud_type: 'cumulus' (classic puffy with flat base), 'fluffy_round', 'rain_cloud'
    """
    half_w = w / 2.0
    half_h = h / 2.0
    bx = cx - half_w
    by = cy - half_h

    if cloud_type == "cumulus" or cloud_type == "rain_cloud":
        # Authentic Cartoon Cumulus Cloud
        d = [
            f"M {format_num(bx + w * 0.18)} {format_num(by + h * 0.88)}",
            # Left puff
            f"C {format_num(bx - w * 0.05)} {format_num(by + h * 0.85)} {format_num(bx - w * 0.04)} {format_num(by + h * 0.45)} {format_num(bx + w * 0.14)} {format_num(by + h * 0.42)}",
            # Top-left puff
            f"C {format_num(bx + w * 0.12)} {format_num(by + h * 0.12)} {format_num(bx + w * 0.38)} {format_num(by + h * 0.10)} {format_num(bx + w * 0.48)} {format_num(by + h * 0.28)}",
            # Main high top-right puff
            f"C {format_num(bx + w * 0.55)} {format_num(by - h * 0.02)} {format_num(bx + w * 0.86)} {format_num(by + h * 0.05)} {format_num(bx + w * 0.88)} {format_num(by + h * 0.40)}",
            # Right puff down to flat base
            f"C {format_num(bx + w * 1.05)} {format_num(by + h * 0.45)} {format_num(bx + w * 1.04)} {format_num(by + h * 0.85)} {format_num(bx + w * 0.82)} {format_num(by + h * 0.88)}",
            "Z"
        ]
        if cloud_type == "rain_cloud":
            drop_len = h * 0.32
            drop_r = max(2.5, w * 0.025)
            drop_xs = [cx - w * 0.26, cx, cx + w * 0.26]
            drop_y = by + h * 0.98 + h * 0.15
            for dx in drop_xs:
                d.append(f"M {format_num(dx)} {format_num(drop_y)} "
                         f"L {format_num(dx - drop_r * 1.5)} {format_num(drop_y + drop_len)} "
                         f"A {format_num(drop_r)} {format_num(drop_r)} 0 1 0 {format_num(dx + drop_r * 1.5)} {format_num(drop_y + drop_len)} Z")
        return " ".join(d)
    else:
        # Fluffy 360-degree round cloud
        d = [
            f"M {format_num(bx + w * 0.18)} {format_num(by + h * 0.78)}",
            f"C {format_num(bx - w * 0.06)} {format_num(by + h * 0.75)} {format_num(bx - w * 0.05)} {format_num(by + h * 0.40)} {format_num(bx + w * 0.14)} {format_num(by + h * 0.38)}",
            f"C {format_num(bx + w * 0.12)} {format_num(by + h * 0.08)} {format_num(bx + w * 0.38)} {format_num(by + h * 0.06)} {format_num(bx + w * 0.48)} {format_num(by + h * 0.24)}",
            f"C {format_num(bx + w * 0.55)} {format_num(by - h * 0.04)} {format_num(bx + w * 0.88)} {format_num(by + h * 0.04)} {format_num(bx + w * 0.88)} {format_num(by + h * 0.36)}",
            f"C {format_num(bx + w * 1.06)} {format_num(by + h * 0.42)} {format_num(bx + w * 1.05)} {format_num(by + h * 0.75)} {format_num(bx + w * 0.82)} {format_num(by + h * 0.78)}",
            f"C {format_num(bx + w * 0.75)} {format_num(by + h * 1.04)} {format_num(bx + w * 0.25)} {format_num(by + h * 1.04)} {format_num(bx + w * 0.18)} {format_num(by + h * 0.78)}",
            "Z"
        ]
        return " ".join(d)

# ----------------------------------------------------------------------------
# 5. ORGANIC BLOBS & LIQUID MORPHS
# ----------------------------------------------------------------------------
def generate_organic_blob(cx: float, cy: float, w: float, h: float,
                          complexity: int = 5, seed: int = 1,
                          contrast: float = 0.28) -> str:
    """
    Generates smooth organic liquid blobs using Catmull-Rom Bezier splines.
    """
    nodes = max(3, min(complexity, 14))
    rx = w / 2.0
    ry = h / 2.0
    
    pts = []
    for i in range(nodes):
        ang = 2.0 * math.pi * i / nodes
        h1 = math.sin(ang * 2.0 + seed * 1.37)
        h2 = math.cos(ang * 3.0 + seed * 2.19)
        h3 = math.sin(ang * 1.0 + seed * 0.73)
        variation = 1.0 + contrast * (h1 * 0.5 + h2 * 0.35 + h3 * 0.15)
        
        px = cx + rx * variation * math.cos(ang)
        py = cy + ry * variation * math.sin(ang)
        pts.append((px, py))

    n = len(pts)
    d = [f"M {format_num(pts[0][0])} {format_num(pts[0][1])}"]
    for i in range(n):
        p0 = pts[(i - 1 + n) % n]
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        p3 = pts[(i + 2) % n]

        cp1_x = p1[0] + (p2[0] - p0[0]) / 6.0
        cp1_y = p1[1] + (p2[1] - p0[1]) / 6.0
        cp2_x = p2[0] - (p3[0] - p1[0]) / 6.0
        cp2_y = p2[1] - (p3[1] - p1[1]) / 6.0

        d.append(f"C {format_num(cp1_x)} {format_num(cp1_y)} {format_num(cp2_x)} {format_num(cp2_y)} {format_num(p2[0])} {format_num(p2[1])}")

    d.append("Z")
    return " ".join(d)

# ----------------------------------------------------------------------------
# 6. BADGES, RIBBONS, SPIRALS, GEARS & SYMBOLS
# ----------------------------------------------------------------------------
def generate_scalloped_badge(cx: float, cy: float, rx: float, ry: float,
                            scallops: int = 16, scallop_depth: float = 0.15) -> str:
    scallops = max(6, min(scallops, 64))
    step = 2.0 * math.pi / scallops
    d = []
    for i in range(scallops):
        ang1 = i * step
        ang2 = (i + 1) * step
        p1 = (cx + rx * math.cos(ang1), cy + ry * math.sin(ang1))
        p2 = (cx + rx * math.cos(ang2), cy + ry * math.sin(ang2))
        mid_ang = (ang1 + ang2) / 2.0
        r_outer = 1.0 + scallop_depth
        cp = (cx + rx * r_outer * math.cos(mid_ang), cy + ry * r_outer * math.sin(mid_ang))
        if i == 0:
            d.append(f"M {format_num(p1[0])} {format_num(p1[1])}")
        d.append(f"Q {format_num(cp[0])} {format_num(cp[1])} {format_num(p2[0])} {format_num(p2[1])}")
    d.append("Z")
    return " ".join(d)

def generate_banner_ribbon(cx: float, cy: float, w: float, h: float) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    notch = w * 0.12
    bx = cx - half_w
    by = cy - half_h
    pts = [
        (bx, by),
        (bx + w, by),
        (bx + w - notch, cy),
        (bx + w, by + h),
        (bx, by + h),
        (bx + notch, cy)
    ]
    return generate_polygon_with_fillets(pts, corner_radius=0.0)

def generate_award_ribbon(cx: float, cy: float, radius: float, scallops: int = 16) -> str:
    """
    Generates a solid award ribbon without overlapping interior holes.
    """
    rcy = cy - radius * 0.25
    rx = radius * 0.75
    ry = radius * 0.75
    scallops = max(8, min(scallops, 48))
    step = 2.0 * math.pi / scallops
    
    d = []
    for i in range(scallops):
        ang1 = i * step
        ang2 = (i + 1) * step
        p1 = (cx + rx * math.cos(ang1), rcy + ry * math.sin(ang1))
        p2 = (cx + rx * math.cos(ang2), rcy + ry * math.sin(ang2))
        mid_ang = (ang1 + ang2) / 2.0
        r_outer = 1.15
        cp = (cx + rx * r_outer * math.cos(mid_ang), rcy + ry * r_outer * math.sin(mid_ang))
        if i == 0:
            d.append(f"M {format_num(p1[0])} {format_num(p1[1])}")
        d.append(f"Q {format_num(cp[0])} {format_num(cp[1])} {format_num(p2[0])} {format_num(p2[1])}")
    d.append("Z")
    
    tail_w = radius * 0.32
    tail_h = radius * 1.05
    top_y = rcy + ry * 0.55
    
    # Left tail
    lt1 = (cx - radius * 0.45, top_y)
    lt2 = (cx - radius * 0.45 + tail_w, top_y)
    lt3 = (cx - radius * 0.18, top_y + tail_h)
    lt4 = (cx - radius * 0.32, top_y + tail_h - radius * 0.18)
    lt5 = (cx - radius * 0.55, top_y + tail_h)
    d.append(f"M {format_num(lt1[0])} {format_num(lt1[1])} L {format_num(lt2[0])} {format_num(lt2[1])} L {format_num(lt3[0])} {format_num(lt3[1])} L {format_num(lt4[0])} {format_num(lt4[1])} L {format_num(lt5[0])} {format_num(lt5[1])} Z")
    
    # Right tail
    rt1 = (cx + radius * 0.45 - tail_w, top_y)
    rt2 = (cx + radius * 0.45, top_y)
    rt3 = (cx + radius * 0.55, top_y + tail_h)
    rt4 = (cx + radius * 0.32, top_y + tail_h - radius * 0.18)
    rt5 = (cx + radius * 0.18, top_y + tail_h)
    d.append(f"M {format_num(rt1[0])} {format_num(rt1[1])} L {format_num(rt2[0])} {format_num(rt2[1])} L {format_num(rt3[0])} {format_num(rt3[1])} L {format_num(rt4[0])} {format_num(rt4[1])} L {format_num(rt5[0])} {format_num(rt5[1])} Z")
    
    return " ".join(d)

def generate_spiral(cx: float, cy: float, max_radius: float,
                    turns: float = 4.0, spiral_type: str = "archimedean") -> str:
    turns = max(0.5, min(turns, 20.0))
    total_angle = turns * 2.0 * math.pi
    num_samples = int(turns * 60)
    pts = []
    for i in range(num_samples + 1):
        theta = total_angle * i / num_samples
        if spiral_type == "archimedean":
            r = max_radius * (theta / total_angle)
        else:
            k = 0.3063489
            r = max_radius * (math.exp(k * theta) - 1.0) / (math.exp(k * total_angle) - 1.0)
        pts.append((cx + r * math.cos(theta), cy + r * math.sin(theta)))

    d = [f"M {format_num(pts[0][0])} {format_num(pts[0][1])}"]
    for p in pts[1:]:
        d.append(f"L {format_num(p[0])} {format_num(p[1])}")
    return " ".join(d)

def generate_gear(cx: float, cy: float, outer_r: float, teeth: int = 12,
                  tooth_depth_ratio: float = 0.25, hole_ratio: float = 0.35) -> str:
    teeth = max(4, min(teeth, 48))
    inner_r = outer_r * (1.0 - clamp(tooth_depth_ratio, 0.1, 0.5))
    step = 2.0 * math.pi / teeth
    pts = []
    for i in range(teeth):
        a0 = i * step
        a1 = a0 + step * 0.25
        a2 = a0 + step * 0.5
        a3 = a0 + step * 0.75
        pts.append((cx + outer_r * math.cos(a0), cy + outer_r * math.sin(a0)))
        pts.append((cx + outer_r * math.cos(a1), cy + outer_r * math.sin(a1)))
        pts.append((cx + inner_r * math.cos(a2), cy + inner_r * math.sin(a2)))
        pts.append((cx + inner_r * math.cos(a3), cy + inner_r * math.sin(a3)))

    gear_outline = generate_polygon_with_fillets(pts, 0.0)
    if hole_ratio > 0.05:
        hole_r = outer_r * clamp(hole_ratio, 0.1, 0.8)
        k = K_BEZIER * hole_r
        hole_path = (
            f" M {format_num(cx - hole_r)} {format_num(cy)} "
            f"C {format_num(cx - hole_r)} {format_num(cy + k)} {format_num(cx - k)} {format_num(cy + hole_r)} {format_num(cx)} {format_num(cy + hole_r)} "
            f"C {format_num(cx + k)} {format_num(cy + hole_r)} {format_num(cx + hole_r)} {format_num(cy + k)} {format_num(cx + hole_r)} {format_num(cy)} "
            f"C {format_num(cx + hole_r)} {format_num(cy - k)} {format_num(cx + k)} {format_num(cy - hole_r)} {format_num(cx)} {format_num(cy - hole_r)} "
            f"C {format_num(cx - k)} {format_num(cy - hole_r)} {format_num(cx - hole_r)} {format_num(cy - k)} {format_num(cx - hole_r)} {format_num(cy)} Z"
        )
        return gear_outline + hole_path
    return gear_outline

def generate_heart(cx: float, cy: float, w: float, h: float) -> str:
    """
    Generates a classic, beautiful, perfectly-proportioned vector heart shape.
    """
    tip_y = cy + h * 0.48
    cleft_y = cy - h * 0.20
    
    return (
        f"M {format_num(cx)} {format_num(tip_y)} "
        f"C {format_num(cx - w * 0.25)} {format_num(cy + h * 0.28)} {format_num(cx - w * 0.50)} {format_num(cy + h * 0.06)} {format_num(cx - w * 0.50)} {format_num(cy - h * 0.12)} "
        f"C {format_num(cx - w * 0.50)} {format_num(cy - h * 0.40)} {format_num(cx - w * 0.24)} {format_num(cy - h * 0.50)} {format_num(cx)} {format_num(cleft_y)} "
        f"C {format_num(cx + w * 0.24)} {format_num(cy - h * 0.50)} {format_num(cx + w * 0.50)} {format_num(cy - h * 0.40)} {format_num(cx + w * 0.50)} {format_num(cy - h * 0.12)} "
        f"C {format_num(cx + w * 0.50)} {format_num(cy + h * 0.06)} {format_num(cx + w * 0.25)} {format_num(cy + h * 0.28)} {format_num(cx)} {format_num(tip_y)} Z"
    )

def generate_cross(cx: float, cy: float, w: float, h: float,
                   arm_thickness_ratio: float = 0.35, corner_radius: float = 0.0) -> str:
    half_w = w / 2.0
    half_h = h / 2.0
    arm_w = half_w * clamp(arm_thickness_ratio, 0.1, 0.8)
    arm_h = half_h * clamp(arm_thickness_ratio, 0.1, 0.8)
    pts = [
        (cx - arm_w, cy - half_h), (cx + arm_w, cy - half_h),
        (cx + arm_w, cy - arm_h), (cx + half_w, cy - arm_h),
        (cx + half_w, cy + arm_h), (cx + arm_w, cy + arm_h),
        (cx + arm_w, cy + half_h), (cx - arm_w, cy + half_h),
        (cx - arm_w, cy + arm_h), (cx - half_w, cy + arm_h),
        (cx - half_w, cy - arm_h), (cx - arm_w, cy - arm_h),
    ]
    return generate_polygon_with_fillets(pts, corner_radius)

def generate_map_pin(cx: float, cy: float, w: float, h: float, hole_ratio: float = 0.35) -> str:
    half_w = w / 2.0
    head_r = half_w
    head_cy = cy - h * 0.15
    tip_y = cy + h / 2.0
    
    k = K_BEZIER * head_r
    pin_outer = (
        f"M {format_num(cx)} {format_num(tip_y)} "
        f"C {format_num(cx - head_r * 0.9)} {format_num(cy + h * 0.15)} {format_num(cx - head_r)} {format_num(head_cy + head_r * 0.5)} {format_num(cx - head_r)} {format_num(head_cy)} "
        f"C {format_num(cx - head_r)} {format_num(head_cy - k)} {format_num(cx - k)} {format_num(head_cy - head_r)} {format_num(cx)} {format_num(head_cy - head_r)} "
        f"C {format_num(cx + k)} {format_num(head_cy - head_r)} {format_num(cx + head_r)} {format_num(head_cy - k)} {format_num(cx + head_r)} {format_num(head_cy)} "
        f"C {format_num(cx + head_r)} {format_num(head_cy + head_r * 0.5)} {format_num(cx + head_r * 0.9)} {format_num(cy + h * 0.15)} {format_num(cx)} {format_num(tip_y)} Z"
    )
    if hole_ratio > 0.05:
        hole_r = head_r * clamp(hole_ratio, 0.1, 0.6)
        k_in = K_BEZIER * hole_r
        hole_path = (
            f" M {format_num(cx - hole_r)} {format_num(head_cy)} "
            f"C {format_num(cx - hole_r)} {format_num(head_cy + k_in)} {format_num(cx - k_in)} {format_num(head_cy + hole_r)} {format_num(cx)} {format_num(head_cy + hole_r)} "
            f"C {format_num(cx + k_in)} {format_num(head_cy + hole_r)} {format_num(cx + hole_r)} {format_num(head_cy + k_in)} {format_num(cx + hole_r)} {format_num(head_cy)} "
            f"C {format_num(cx + hole_r)} {format_num(head_cy - k_in)} {format_num(cx + k_in)} {format_num(head_cy - hole_r)} {format_num(cx)} {format_num(head_cy - hole_r)} "
            f"C {format_num(cx - k_in)} {format_num(head_cy - hole_r)} {format_num(cx - hole_r)} {format_num(head_cy - k_in)} {format_num(cx - hole_r)} {format_num(head_cy)} Z"
        )
        return pin_outer + hole_path
    return pin_outer
