"""Region outline and fill pattern generation service."""

from __future__ import annotations

import math
import random

from avge_engine.scene import CurveConstraints, Style
from avge_engine.services import procedural_service as line_tools


def sample_region_outline(region, samples_per_segment: int = 8) -> list[list[float]]:
    """Return a dense closed outline suitable for patterned primitive borders."""
    if region.primitive:
        p = region.primitive
        ptype = p.get("type")
        if ptype == "rect":
            x, y, w, h = p["x"], p["y"], p["width"], p["height"]
            return [[x, y], [x + w, y], [x + w, y + h], [x, y + h], [x, y]]
        if ptype == "ellipse":
            cx, cy, rx, ry = p["cx"], p["cy"], p["rx"], p["ry"]
            n = max(24, samples_per_segment * 8)
            return [
                [cx + math.cos(math.tau * i / n) * rx, cy + math.sin(math.tau * i / n) * ry]
                for i in range(n + 1)
            ]
    pts = [[float(x), float(y)] for x, y in region.outline]
    if pts and region.constraints.closed and pts[0] != pts[-1]:
        pts.append(list(pts[0]))
    return pts


def apply_primitive_patterns(
    scene,
    doc_id: str,
    base_region,
    outline_pattern: str | None,
    fill_pattern: str | None,
    pattern_density: int,
    pattern_amplitude: float,
    pattern_jitter: float,
    pattern_seed: int,
    stroke: str | None,
    pattern_width: float,
    pattern_opacity: float | None,
    layer: str,
    z_index: int,
) -> list[str]:
    """Create line-pattern overlays for a primitive outline and/or clipped fill."""
    created: list[str] = []
    color = stroke or "#333333"
    opacity = pattern_opacity

    if outline_pattern in ("dashed", "dotted"):
        dash = "1,5" if outline_pattern == "dotted" else "7,5"
        sampled = sample_region_outline(base_region)
        r = scene.create_line(
            points=sampled,
            document_id=doc_id,
            region_id=f"{base_region.id}_{outline_pattern}_outline",
            layer=layer,
            z_index=z_index + 2,
            stroke=color,
            stroke_width=pattern_width,
            opacity=opacity if opacity is not None else 1.0,
            stroke_linecap="round" if outline_pattern == "dotted" else "butt",
            stroke_dasharray=dash,
            smoothness=0.0 if len(sampled) <= 6 else 0.65,
        )
        r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
        created.append(r.id)
    elif outline_pattern in ("wavy", "zigzag", "rough", "sketch", "tapered", "pressure"):
        sampled = sample_region_outline(base_region)
        rng = random.Random(pattern_seed)
        if outline_pattern in ("rough", "sketch"):
            repeats = 2 if outline_pattern == "sketch" else 1
            for i in range(repeats):
                pts = line_tools._jitter_points(sampled, max(pattern_jitter, pattern_amplitude * 0.45), rng)
                r = scene.create_line(
                    points=pts,
                    document_id=doc_id,
                    region_id=f"{base_region.id}_{outline_pattern}_outline_{i:02d}",
                    layer=layer,
                    z_index=z_index + 2 + i,
                    stroke=color,
                    stroke_width=pattern_width * (0.8 + i * 0.2),
                    opacity=opacity if opacity is not None else (0.55 if outline_pattern == "sketch" else 0.75),
                    stroke_linecap="round",
                    smoothness=0.55,
                )
                r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
                created.append(r.id)
        elif outline_pattern in ("tapered", "pressure"):
            widths = line_tools._width_profile_values(
                len(sampled),
                outline_pattern,
                pattern_width * 2.2,
                max(0.001, pattern_width * 0.35),
                pattern_width,
            )
            ribbon = line_tools._ribbon_outline(sampled, widths)
            r = scene.create_region(
                outline=ribbon,
                document_id=doc_id,
                region_id=f"{base_region.id}_{outline_pattern}_outline",
                layer=layer,
                z_index=z_index + 2,
                constraints=CurveConstraints(smoothness=0.55, closed=True),
                style=Style(fill=color, stroke=None, opacity=opacity if opacity is not None else 0.85),
                metadata={"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id},
            )
            created.append(r.id)
        else:
            subpaths = []
            for i in range(len(sampled) - 1):
                subpaths.append(line_tools._line_pattern_points(
                    outline_pattern,
                    [sampled[i], sampled[i + 1]],
                    None,
                    0.1,
                    1.0,
                    max(4, int(pattern_density)),
                    pattern_amplitude,
                    1.0,
                ))
            r = scene.create_compound_path(
                subpaths=subpaths,
                document_id=doc_id,
                region_id=f"{base_region.id}_{outline_pattern}_outline",
                layer=layer,
                z_index=z_index + 2,
                fill=None,
                stroke=color,
                stroke_width=pattern_width,
                opacity=opacity if opacity is not None else 1.0,
                stroke_linecap="round",
                smoothness=0.65 if outline_pattern == "wavy" else 0.0,
                closed=False,
            )
            r.metadata.update({"tool": "create_region_pattern", "pattern": outline_pattern, "base": base_region.id})
            created.append(r.id)

    if base_region.constraints.closed and fill_pattern in ("hatch", "cross_hatch", "contour_hatch", "scribble", "stipple"):
        b = base_region.bounds
        if b:
            bounds = [b["x"], b["y"], b["w"], b["h"]]
            rng = random.Random(pattern_seed)
            if fill_pattern in ("hatch", "cross_hatch", "contour_hatch"):
                subpaths = line_tools._hatch_subpaths(
                    bounds, pattern_density, 25.0, fill_pattern, pattern_amplitude, pattern_jitter, rng
                )
                r = scene.create_compound_path(
                    subpaths=subpaths,
                    document_id=doc_id,
                    region_id=f"{base_region.id}_{fill_pattern}_fill",
                    layer=layer,
                    z_index=z_index + 1,
                    fill=None,
                    stroke=color,
                    stroke_width=pattern_width,
                    opacity=opacity if opacity is not None else 0.45,
                    stroke_linecap="round",
                    smoothness=0.55 if fill_pattern == "contour_hatch" else 0.0,
                    closed=False,
                )
                r.clip_to = base_region.id
                r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                created.append(r.id)
            elif fill_pattern == "scribble":
                for i, pts in enumerate(line_tools._scribble_paths(bounds, pattern_density, pattern_jitter, rng)):
                    r = scene.create_line(
                        points=pts,
                        document_id=doc_id,
                        region_id=f"{base_region.id}_{fill_pattern}_{i:02d}",
                        layer=layer,
                        z_index=z_index + 1,
                        stroke=color,
                        stroke_width=pattern_width * rng.uniform(0.65, 1.25),
                        opacity=opacity if opacity is not None else 0.45,
                        stroke_linecap="round",
                        smoothness=0.65,
                    )
                    r.clip_to = base_region.id
                    r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                    created.append(r.id)
            elif fill_pattern == "stipple":
                total = max(1, min(600, int(pattern_density)))
                for i in range(total):
                    dot_w = pattern_width * rng.uniform(0.7, 1.6)
                    r = scene.create_ellipse(
                        b["x"] + rng.random() * b["w"],
                        b["y"] + rng.random() * b["h"],
                        dot_w,
                        dot_w,
                        document_id=doc_id,
                        region_id=f"{base_region.id}_{fill_pattern}_{i:03d}",
                        layer=layer,
                        z_index=z_index + 1,
                        fill=color,
                        stroke=None,
                        opacity=opacity if opacity is not None else rng.uniform(0.25, 0.65),
                    )
                    r.clip_to = base_region.id
                    r.metadata.update({"tool": "create_region_pattern", "pattern": fill_pattern, "base": base_region.id})
                    created.append(r.id)

    if created:
        scene._persist(doc_id)
    return created
