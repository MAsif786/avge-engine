"""Perspective-aware scene construction services."""
from __future__ import annotations

import random

from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import FacadeGridResult, PerspectiveGridResult, SurfaceStripesResult
from avge_engine.services.engine import get_graph, resolve_doc, stroke_width_to_norm


class SceneConstructionService:
    """Application service for perspective grids, facade windows, and surface stripes."""

    def __init__(self, graph=None) -> None:
        self.graph = graph or get_graph()

    def create_perspective_grid(
        self,
        *,
        vanishing_points: list[list[float]],
        horizon_y: float = 0.5,
        document_id: str | None = None,
        region_id: str | None = None,
        verticals: int = 9,
        horizontals: int = 9,
        bounds: list[float] | None = None,
        include_horizon: bool = True,
        layer: str = "guides",
        z_index: int = -100,
        stroke: str = "#55C7FF",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 0.35,
    ) -> PerspectiveGridResult:
        """Create two-point perspective construction guide regions."""
        doc_id = resolve_doc(document_id)
        if len(vanishing_points) != 2:
            raise ValueError("vanishing_points must contain exactly two [x,y] points")
        vp_l = [float(vanishing_points[0][0]), float(vanishing_points[0][1])]
        vp_r = [float(vanishing_points[1][0]), float(vanishing_points[1][1])]
        x0, y0, x1, y1 = [float(v) for v in (bounds or [0.0, 0.0, 1.0, 1.0])]
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bounds must be [x0,y0,x1,y1] with positive size")

        resolved_stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.001
        subpaths: list[list[list[float]]] = []
        vertical_count = max(2, int(verticals))
        horizontal_count = max(2, int(horizontals))
        for i in range(vertical_count):
            x = x0 + (x1 - x0) * (i / (vertical_count - 1))
            subpaths.append([[x, y0], [x, y1]])
        for i in range(horizontal_count):
            y = y0 + (y1 - y0) * (i / (horizontal_count - 1))
            left_line = _clip_line_to_bounds(vp_l, [x1, y], (x0, y0, x1, y1))
            right_line = _clip_line_to_bounds(vp_r, [x0, y], (x0, y0, x1, y1))
            if left_line:
                subpaths.append(left_line)
            if right_line:
                subpaths.append(right_line)

        rid = region_id or "perspective_grid"
        grid = self.graph.create_compound_path(
            subpaths=subpaths,
            document_id=doc_id,
            region_id=rid,
            layer=layer,
            z_index=z_index,
            fill=None,
            stroke=stroke,
            stroke_width=resolved_stroke_width,
            opacity=_clamp01(opacity),
            smoothness=0.0,
            closed=False,
        )
        ids = [grid.id]
        if include_horizon:
            horizon = self.graph.create_line(
                points=[[x0, horizon_y], [x1, horizon_y]],
                document_id=doc_id,
                region_id=f"{rid}_horizon",
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=resolved_stroke_width,
                opacity=_clamp01(opacity * 1.25),
                smoothness=0.0,
            )
            ids.append(horizon.id)
        return PerspectiveGridResult(ids=ids, vp_left=vp_l, vp_right=vp_r, horizon_y=horizon_y)

    def create_facade_grid(
        self,
        *,
        target_quad: list[list[float]],
        rows: int,
        columns: int,
        document_id: str | None = None,
        region_id: str | None = None,
        layer: str = "architecture",
        z_index: int = 0,
        facade_fill: str = "#2C3542",
        facade_stroke: str = "#0A1018",
        window_fill: str = "#182536",
        lit_fill: str = "#FFE8A3",
        window_stroke: str | None = "#A9C8D6",
        stroke_width: StrokeWidthInput = None,
        opacity: float = 1.0,
        lit_ratio: float = 0.22,
        margin_u: float = 0.18,
        margin_v: float = 0.18,
        variation: float = 0.08,
        seed: int = 1,
        create_base: bool = True,
    ) -> FacadeGridResult:
        """Create a perspective facade panel plus individually editable window regions."""
        doc_id = resolve_doc(document_id)
        if len(target_quad) != 4:
            raise ValueError("target_quad must contain exactly four [x,y] points")
        if rows < 1 or columns < 1:
            raise ValueError("rows and columns must be >= 1")

        quad = [[float(p[0]), float(p[1])] for p in target_quad]
        resolved_stroke_width = stroke_width_to_norm(doc_id, stroke_width) or 0.001
        prefix = region_id or "facade"
        rng = random.Random(seed)
        created: list[str] = []

        if create_base:
            base = self.graph.project_quad(
                quad,
                document_id=doc_id,
                region_id=prefix,
                layer=layer,
                z_index=z_index,
                fill=facade_fill,
                stroke=facade_stroke,
                stroke_width=resolved_stroke_width,
                opacity=opacity,
                metadata={"tool": "create_facade_grid", "part": "facade"},
            )
            created.append(base.id)

        for row in range(rows):
            for col in range(columns):
                cell_noise = (rng.random() - 0.5) * max(0.0, variation)
                mu = _clamp01(margin_u + cell_noise)
                mv = _clamp01(margin_v - cell_noise * 0.5)
                win_quad = _cell_quad(
                    quad,
                    col / columns,
                    row / rows,
                    (col + 1) / columns,
                    (row + 1) / rows,
                    mu,
                    mv,
                )
                lit = rng.random() < _clamp01(lit_ratio)
                rid = f"{prefix}_w{row:02d}_{col:02d}"
                win = self.graph.project_quad(
                    win_quad,
                    document_id=doc_id,
                    region_id=rid,
                    layer=layer,
                    z_index=z_index + 1,
                    fill=lit_fill if lit else window_fill,
                    stroke=window_stroke,
                    stroke_width=resolved_stroke_width,
                    opacity=opacity,
                    metadata={
                        "tool": "create_facade_grid",
                        "part": "window",
                        "facade": prefix,
                        "row": row,
                        "column": col,
                        "lit": lit,
                    },
                )
                created.append(win.id)

        return FacadeGridResult(
            prefix=prefix,
            windows=rows * columns,
            lit_ratio=lit_ratio,
            region_count=len(created),
        )

    def create_surface_stripes(
        self,
        *,
        target_quad: list[list[float]],
        count: int,
        document_id: str | None = None,
        region_id: str | None = None,
        orientation: str = "u",
        start: float = 0.08,
        end: float = 0.92,
        stripe_width: float = 0.05,
        gap: float | None = None,
        spacing_falloff: float = 1.0,
        fill: str = "#F1F7F8",
        stroke: str | None = None,
        stroke_width: StrokeWidthInput = None,
        opacity: float = 0.95,
        layer: str = "road",
        z_index: int = 0,
    ) -> SurfaceStripesResult:
        """Create perspective-correct stripes on a quadrilateral surface."""
        doc_id = resolve_doc(document_id)
        if len(target_quad) != 4:
            raise ValueError("target_quad must contain exactly four points")
        count = max(1, min(100, int(count)))
        resolved_stroke_width = stroke_width_to_norm(doc_id, stroke_width)
        prefix = region_id or "surface_stripe"
        start = _clamp01(start)
        end = _clamp01(end)
        if end <= start:
            raise ValueError("end must be greater than start")
        if gap is None:
            gap = max(0.0, (end - start - stripe_width * count) / max(1, count - 1))

        pos = start
        created: list[str] = []
        for i in range(count):
            w = max(0.001, stripe_width * (spacing_falloff ** i if spacing_falloff < 1.0 else 1.0))
            p0 = pos
            p1 = min(end, pos + w)
            if p1 <= p0:
                break
            if orientation == "u":
                quad = [
                    _quad_point(target_quad, p0, 0.0),
                    _quad_point(target_quad, p1, 0.0),
                    _quad_point(target_quad, p1, 1.0),
                    _quad_point(target_quad, p0, 1.0),
                ]
            else:
                quad = [
                    _quad_point(target_quad, 0.0, p0),
                    _quad_point(target_quad, 1.0, p0),
                    _quad_point(target_quad, 1.0, p1),
                    _quad_point(target_quad, 0.0, p1),
                ]
            region = self.graph.project_quad(
                quad,
                document_id=doc_id,
                region_id=f"{prefix}_{i:02d}",
                layer=layer,
                z_index=z_index + i,
                fill=fill,
                stroke=stroke,
                stroke_width=resolved_stroke_width,
                opacity=opacity,
                metadata={"tool": "create_surface_stripes", "stripe_index": i},
            )
            created.append(region.id)
            pos = p1 + gap * (spacing_falloff ** i)
            if pos >= end:
                break
        return SurfaceStripesResult(ids=created)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _lerp_point(a: list[float] | tuple[float, float], b: list[float] | tuple[float, float], t: float) -> list[float]:
    return [float(a[0]) + (float(b[0]) - float(a[0])) * t, float(a[1]) + (float(b[1]) - float(a[1])) * t]


def _quad_point(quad: list[list[float]], u: float, v: float) -> list[float]:
    top = _lerp_point(quad[0], quad[1], u)
    bottom = _lerp_point(quad[3], quad[2], u)
    return _lerp_point(top, bottom, v)


def _cell_quad(
    quad: list[list[float]],
    u0: float,
    v0: float,
    u1: float,
    v1: float,
    margin_u: float,
    margin_v: float,
) -> list[list[float]]:
    du = max(0.0, u1 - u0)
    dv = max(0.0, v1 - v0)
    uu0 = u0 + du * margin_u
    uu1 = u1 - du * margin_u
    vv0 = v0 + dv * margin_v
    vv1 = v1 - dv * margin_v
    return [
        _quad_point(quad, uu0, vv0),
        _quad_point(quad, uu1, vv0),
        _quad_point(quad, uu1, vv1),
        _quad_point(quad, uu0, vv1),
    ]


def _clip_line_to_bounds(
    p1: list[float],
    p2: list[float],
    bounds: tuple[float, float, float, float],
) -> list[list[float]] | None:
    """Clip an infinite line through p1/p2 to an axis-aligned bounds rectangle."""
    x0, y0, x1, y1 = bounds
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return None

    hits: list[tuple[float, list[float]]] = []
    if abs(dx) > 1e-9:
        for x in (x0, x1):
            t = (x - p1[0]) / dx
            y = p1[1] + dy * t
            if y0 - 1e-9 <= y <= y1 + 1e-9:
                hits.append((t, [x, y]))
    if abs(dy) > 1e-9:
        for y in (y0, y1):
            t = (y - p1[1]) / dy
            x = p1[0] + dx * t
            if x0 - 1e-9 <= x <= x1 + 1e-9:
                hits.append((t, [x, y]))

    unique: list[tuple[float, list[float]]] = []
    for t, pt in sorted(hits, key=lambda item: item[0]):
        if not any(abs(pt[0] - u[1][0]) < 1e-6 and abs(pt[1] - u[1][1]) < 1e-6 for u in unique):
            unique.append((t, pt))
    if len(unique) < 2:
        return None
    return [unique[0][1], unique[-1][1]]
