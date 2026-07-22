"""Procedural drawing application service.

Controllers keep MCP/API schemas and response text; this service owns scene
mutation and procedural orchestration that is shared by tool wrappers.
"""

from __future__ import annotations

import random

from avge_engine.geometry.line_patterns import (
    hatch_subpaths,
    jitter_points,
    line_pattern_points,
    resolve_bounds,
    ribbon_outline,
    role_dash,
    role_opacity,
    scribble_paths,
    width_profile_values,
)
from avge_engine.scene import CurveConstraints, Style
from avge_engine.services.base import BaseService
from avge_engine.services.engine import StrokeWidthInput, resolve_doc, stroke_width_to_norm


class ProceduralService(BaseService):
    """Application service for procedural drawing tools."""

    def create_line_pattern(
        self,
        *,
        pattern: str,
        document_id: str | None = None,
        element_id: str | None = None,
        points: list[list[float]] | None = None,
        bounds: list[float] | None = None,
        center: list[float] | None = None,
        radius: float = 0.15,
        turns: float = 2.0,
        count: int = 12,
        amplitude: float = 0.025,
        frequency: float = 6.0,
        angle: float = 0.0,
        jitter: float = 0.0,
        density: int = 16,
        seed: int = 1,
        stroke: str | None = "#333333",
        stroke_width: StrokeWidthInput = None,
        opacity: float | None = None,
        linecap: str = "round",
        dash: str | None = None,
        width_profile: str = "uniform",
        start_width: StrokeWidthInput = None,
        end_width: StrokeWidthInput = None,
        layer: str = "linework",
        z_index: int = 0,
        smoothness: float = 0.45,
        role: str = "art",
    ) -> str:
        """Create procedural linework and return the created element IDs."""
        try:
            doc_id = resolve_doc(document_id)
        except RuntimeError:
            return "Error: No active document. Call create_document first."

        base_width = stroke_width_to_norm(doc_id, stroke_width) or 0.005
        start_norm = stroke_width_to_norm(doc_id, start_width) or base_width
        end_norm = stroke_width_to_norm(doc_id, end_width) or max(0.001, base_width * 0.25)
        resolved_opacity = role_opacity(role, opacity)
        resolved_dash = dash if dash is not None else role_dash(role, pattern)
        prefix = element_id or f"line_pattern_{abs(hash((pattern, seed, count))) & 0xFFFF:x}"

        try:
            created: list[str] = []
            if pattern in ("straight", "curve", "wavy", "zigzag", "spiral"):
                path = line_pattern_points(pattern, points, center, radius, turns, count, amplitude, frequency)
                path = jitter_points(path, jitter, random.Random(seed))
                if width_profile == "uniform":
                    r = self.graph.create_line(
                        points=path,
                        document_id=doc_id,
                        element_id=prefix,
                        layer=layer,
                        z_index=z_index,
                        stroke=stroke,
                        stroke_width=base_width,
                        opacity=resolved_opacity,
                        stroke_linecap=linecap,
                        stroke_dasharray=resolved_dash,
                        smoothness=smoothness if pattern != "zigzag" else 0.0,
                    )
                else:
                    widths = width_profile_values(len(path), width_profile, start_norm, end_norm, base_width)
                    outline = ribbon_outline(path, widths)
                    r = self.graph.create_element(
                        outline=outline,
                        document_id=doc_id,
                        element_id=prefix,
                        layer=layer,
                        z_index=z_index,
                        constraints=CurveConstraints(smoothness=smoothness, closed=True),
                        style=Style(fill=stroke, stroke=None, opacity=resolved_opacity),
                        metadata={"tool": "create_line_pattern", "pattern": pattern, "role": role, "width_profile": width_profile},
                    )
                r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role, "width_profile": width_profile})
                created.append(r.id)
            elif pattern in ("hatch", "cross_hatch", "contour_hatch"):
                subpaths = hatch_subpaths(bounds, density, angle, pattern, amplitude, jitter, random.Random(seed))
                r = self.graph.create_compound_path(
                    subpaths=subpaths,
                    document_id=doc_id,
                    element_id=prefix,
                    layer=layer,
                    z_index=z_index,
                    fill=None,
                    stroke=stroke,
                    stroke_width=base_width,
                    opacity=resolved_opacity,
                    stroke_linecap=linecap,
                    stroke_dasharray=resolved_dash,
                    smoothness=smoothness if pattern == "contour_hatch" else 0.0,
                    closed=False,
                )
                r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                created.append(r.id)
            elif pattern == "scribble":
                rng = random.Random(seed)
                for i, path in enumerate(scribble_paths(bounds, count, jitter, rng)):
                    r = self.graph.create_line(
                        points=path,
                        document_id=doc_id,
                        element_id=f"{prefix}_{i:02d}",
                        layer=layer,
                        z_index=z_index,
                        stroke=stroke,
                        stroke_width=base_width * rng.uniform(0.65, 1.25),
                        opacity=resolved_opacity,
                        stroke_linecap=linecap,
                        smoothness=0.65,
                    )
                    r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                    created.append(r.id)
            elif pattern == "stipple":
                rng = random.Random(seed)
                x, y, w, h = resolve_bounds(bounds)
                total = max(1, min(600, int(density if density else count)))
                for i in range(total):
                    px = x + rng.random() * w
                    py = y + rng.random() * h
                    dot_w = base_width * rng.uniform(0.7, 1.6)
                    r = self.graph.create_ellipse(
                        px,
                        py,
                        dot_w,
                        dot_w,
                        document_id=doc_id,
                        element_id=f"{prefix}_{i:03d}",
                        layer=layer,
                        z_index=z_index,
                        fill=stroke,
                        stroke=None,
                        opacity=resolved_opacity * rng.uniform(0.55, 1.0),
                    )
                    r.metadata.update({"tool": "create_line_pattern", "pattern": pattern, "role": role})
                    created.append(r.id)
            else:
                return f"Error: Unknown line pattern '{pattern}'"
        except (ValueError, RuntimeError, TypeError) as e:
            return f"Error: {e}"

        self.graph._persist(doc_id)
        return (
            f"Line pattern created: pattern={pattern}, elements={len(created)}, "
            f"width_profile={width_profile}, role={role}, ids={', '.join(created[:6])}"
        )
