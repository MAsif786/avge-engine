"""Perspective-aware scene construction services."""
from __future__ import annotations

import random
import uuid

from avge_engine.document import CurveConstraints, ElementNode, Style
from avge_engine.geometry import Point2D, normalize_outline
from avge_engine.geometry.perspective import normalize_points_to_unit, project_unit_points, rectangle_grid_points
from avge_engine.geometry.quad import cell_quad, clip_line_to_bounds, quad_point
from avge_engine.schemas.common import StrokeWidthInput
from avge_engine.schemas.service_results import FacadeGridResult, PerspectiveGridResult, SurfaceStripesResult
from avge_engine.services.base_element import BaseElementService
from avge_engine.utils.math_utils import clamp01


class SceneConstructionService(BaseElementService):
    """Application service for perspective grids, facade windows, and surface stripes."""

    def project_quad(
        self,
        target_quad: list[Point2D],
        document_id: str | None = None,
        *,
        element_id: str | None = None,
        source_element_id: str | None = None,
        replace_source: bool = False,
        columns: int = 1,
        rows: int = 1,
        layer: str = "default",
        z_index: int = 0,
        fill: str | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float | None = 0.005,
        opacity: float | None = 1.0,
        blend_mode: str | None = None,
        smoothness: float = 0.0,
        metadata: dict[str, object] | None = None,
    ) -> ElementNode:
        """Create or warp geometry into a target quadrilateral."""
        doc_id = self.require_document_id(document_id)
        if len(target_quad) != 4:
            raise ValueError("target_quad must contain exactly four points")

        quad = [(float(x), float(y)) for x, y in target_quad]
        if source_element_id:
            source = self.get_element(doc_id, source_element_id)
            outline = project_unit_points(normalize_points_to_unit(list(source.outline)), quad)
            base_style = source.style
            out_fill = fill if fill is not None else base_style.fill
            out_stroke = stroke if stroke is not None else base_style.stroke
            out_stroke_width = stroke_width if stroke_width is not None else base_style.stroke_width
            out_opacity = opacity if opacity is not None else base_style.opacity
            out_blend = blend_mode if blend_mode is not None else base_style.blend_mode
            out_layer = layer if layer != "default" else source.layer
            out_z = z_index if z_index != 0 else source.z_index
        else:
            outline = project_unit_points(rectangle_grid_points(columns, rows), quad)
            out_fill = fill
            out_stroke = stroke
            out_stroke_width = stroke_width
            out_opacity = opacity
            out_blend = blend_mode
            out_layer = layer
            out_z = z_index

        if source_element_id and replace_source:
            from avge_engine.services.element_service import ElementService

            ElementService(self.graph).edit_element(
                element_id=source_element_id,
                document_id=doc_id,
                outline=outline,
                smoothness=smoothness,
                fill=out_fill,
                stroke=out_stroke,
                stroke_width=out_stroke_width,
                opacity=out_opacity,
                z_index=out_z,
                blend_mode=out_blend,
                layer=out_layer,
                tags=metadata,
            )
            return self.get_element(doc_id, source_element_id)

        result_id = element_id or f"quad_{uuid.uuid4().hex[:6]}"
        element = self.documents.create_element_node(
            doc_id,
            element_id=result_id,
            layer=out_layer,
            z_index=out_z,
            outline=normalize_outline(outline),
            constraints=CurveConstraints(smoothness=max(0.0, min(1.0, smoothness)), closed=True),
            style=Style(
                fill=None if out_fill is None or out_fill == "none" else out_fill,
                stroke=None if out_stroke is None or out_stroke == "none" else out_stroke,
                stroke_width=max(0.001, min(0.1, out_stroke_width if out_stroke_width is not None else 0.005)),
                opacity=max(0.0, min(1.0, out_opacity if out_opacity is not None else 1.0)),
                blend_mode=out_blend,
            ),
            metadata=metadata or {},
        )
        self.commit(doc_id, action="project_quad", target=element.id)
        return element

    def create_perspective_grid(
        self,
        *,
        vanishing_points: list[list[float]],
        horizon_y: float = 0.5,
        document_id: str | None = None,
        element_id: str | None = None,
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
        """Create two-point perspective construction guide elements."""
        doc_id = self.require_document_id(document_id)
        if len(vanishing_points) != 2:
            raise ValueError("vanishing_points must contain exactly two [x,y] points")
        vp_l = [float(vanishing_points[0][0]), float(vanishing_points[0][1])]
        vp_r = [float(vanishing_points[1][0]), float(vanishing_points[1][1])]
        x0, y0, x1, y1 = [float(v) for v in (bounds or [0.0, 0.0, 1.0, 1.0])]
        if x1 <= x0 or y1 <= y0:
            raise ValueError("bounds must be [x0,y0,x1,y1] with positive size")

        resolved_stroke_width = self.stroke_width_to_norm(doc_id, stroke_width) or 0.001
        subpaths: list[list[list[float]]] = []
        vertical_count = max(2, int(verticals))
        horizontal_count = max(2, int(horizontals))
        for i in range(vertical_count):
            x = x0 + (x1 - x0) * (i / (vertical_count - 1))
            subpaths.append([[x, y0], [x, y1]])
        for i in range(horizontal_count):
            y = y0 + (y1 - y0) * (i / (horizontal_count - 1))
            left_line = clip_line_to_bounds(vp_l, [x1, y], (x0, y0, x1, y1))
            right_line = clip_line_to_bounds(vp_r, [x0, y], (x0, y0, x1, y1))
            if left_line:
                subpaths.append(left_line)
            if right_line:
                subpaths.append(right_line)

        rid = element_id or "perspective_grid"
        grid = self.documents.create_compound_path(
            doc_id,
            subpaths=subpaths,
            element_id=rid,
            layer=layer,
            z_index=z_index,
            fill=None,
            stroke=stroke,
            stroke_width=resolved_stroke_width,
            opacity=clamp01(opacity),
            smoothness=0.0,
            closed=False,
        )
        self.commit(doc_id, action="create_perspective_grid", target=grid.id)
        ids = [grid.id]
        if include_horizon:
            horizon = self.documents.create_line(
                doc_id,
                points=[[x0, horizon_y], [x1, horizon_y]],
                element_id=f"{rid}_horizon",
                layer=layer,
                z_index=z_index,
                stroke=stroke,
                stroke_width=resolved_stroke_width,
                opacity=clamp01(opacity * 1.25),
                smoothness=0.0,
            )
            self.commit(doc_id, action="create_perspective_grid", target=horizon.id)
            ids.append(horizon.id)
        return PerspectiveGridResult(ids=ids, vp_left=vp_l, vp_right=vp_r, horizon_y=horizon_y)

    def create_facade_grid(
        self,
        *,
        target_quad: list[list[float]],
        rows: int,
        columns: int,
        document_id: str | None = None,
        element_id: str | None = None,
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
        """Create a perspective facade panel plus individually editable window elements."""
        doc_id = self.require_document_id(document_id)
        if len(target_quad) != 4:
            raise ValueError("target_quad must contain exactly four [x,y] points")
        if rows < 1 or columns < 1:
            raise ValueError("rows and columns must be >= 1")

        quad = [[float(p[0]), float(p[1])] for p in target_quad]
        resolved_stroke_width = self.stroke_width_to_norm(doc_id, stroke_width) or 0.001
        prefix = element_id or "facade"
        rng = random.Random(seed)
        created: list[str] = []

        if create_base:
            base = self.project_quad(
                quad,
                document_id=doc_id,
                element_id=prefix,
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
                mu = clamp01(margin_u + cell_noise)
                mv = clamp01(margin_v - cell_noise * 0.5)
                win_quad = cell_quad(
                    quad,
                    col / columns,
                    row / rows,
                    (col + 1) / columns,
                    (row + 1) / rows,
                    mu,
                    mv,
                )
                lit = rng.random() < clamp01(lit_ratio)
                rid = f"{prefix}_w{row:02d}_{col:02d}"
                win = self.project_quad(
                    win_quad,
                    document_id=doc_id,
                    element_id=rid,
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
            element_count=len(created),
        )

    def create_surface_stripes(
        self,
        *,
        target_quad: list[list[float]],
        count: int,
        document_id: str | None = None,
        element_id: str | None = None,
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
        doc_id = self.require_document_id(document_id)
        if len(target_quad) != 4:
            raise ValueError("target_quad must contain exactly four points")
        count = max(1, min(100, int(count)))
        resolved_stroke_width = self.stroke_width_to_norm(doc_id, stroke_width)
        prefix = element_id or "surface_stripe"
        start = clamp01(start)
        end = clamp01(end)
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
                    quad_point(target_quad, p0, 0.0),
                    quad_point(target_quad, p1, 0.0),
                    quad_point(target_quad, p1, 1.0),
                    quad_point(target_quad, p0, 1.0),
                ]
            else:
                quad = [
                    quad_point(target_quad, 0.0, p0),
                    quad_point(target_quad, 1.0, p0),
                    quad_point(target_quad, 1.0, p1),
                    quad_point(target_quad, 0.0, p1),
                ]
            element = self.project_quad(
                quad,
                document_id=doc_id,
                element_id=f"{prefix}_{i:02d}",
                layer=layer,
                z_index=z_index + i,
                fill=fill,
                stroke=stroke,
                stroke_width=resolved_stroke_width,
                opacity=opacity,
                metadata={"tool": "create_surface_stripes", "stripe_index": i},
            )
            created.append(element.id)
            pos = p1 + gap * (spacing_falloff ** i)
            if pos >= end:
                break
        return SurfaceStripesResult(ids=created)
