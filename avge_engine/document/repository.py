"""Document repository facade over the current in-memory documents.

Services should depend on this repository instead of reaching into private
persistence/session details. The implementation can later swap the
backing store to SQLite/chunked storage without changing service call sites.
"""
from __future__ import annotations

import uuid
from typing import Any
from types import ModuleType

from avge_engine.geometry import CurveConstraints, Point2D, Transform, normalize_outline
from avge_engine.effects import GradientDef, Style
from avge_engine.document.models import DocumentNode, ElementNode
from avge_engine.document.session import DocumentSessionManager


class DocumentRepository:
    """Read, mutate, and commit documents in the active engine store."""

    def __init__(self, graph: ModuleType, session: DocumentSessionManager | None = None) -> None:
        self.graph = graph
        self.session = session or DocumentSessionManager(graph)

    def resolve_id(self, document_id: str | None = None) -> str:
        """Resolve an explicit document ID or the current MCP active document."""
        return self.session.resolve_id(document_id)

    def require_id(self, document_id: str | None = None) -> str:
        """Resolve a document ID and require it to exist in memory."""
        return self.session.require_loaded_id(document_id)

    def has(self, document_id: str | None = None) -> bool:
        return self.session.has_loaded(document_id)

    def get(self, document_id: str | None = None) -> DocumentNode:
        return self.graph.get_document(self.require_id(document_id))

    def load(self, document_id: str) -> bool:
        return self.session.load_from_storage(document_id)

    def delete(self, document_id: str) -> bool:
        return self.graph.delete_document(document_id)

    def list_stored(self) -> list[dict[str, Any]]:
        return self.graph.list_stored_documents()

    def get_element(self, document_id: str, element_id: str) -> ElementNode:
        elements = self.elements(document_id)
        element = elements.get(element_id)
        if element is None:
            raise ValueError(f"Element '{element_id}' not found in document '{document_id}'")
        return element

    def has_element(self, document_id: str, element_id: str) -> bool:
        return element_id in self.elements(document_id)

    def list_elements(self, document_id: str) -> list[ElementNode]:
        return list(self.elements(document_id).values())

    def elements(self, document_id: str) -> dict[str, ElementNode]:
        """Return the mutable element map for a loaded document."""
        return self.get(document_id).elements()

    def add_element(self, document_id: str, element: ElementNode) -> None:
        elements = self.elements(document_id)
        if element.id in elements:
            raise ValueError(f"Element '{element.id}' already exists in document '{document_id}'")
        elements[element.id] = element

    def create_element_node(
        self,
        document_id: str,
        *,
        element_id: str,
        outline: list[Point2D],
        layer: str = "default",
        z_index: int = 0,
        clip_to: str | None = None,
        constraints: CurveConstraints | None = None,
        style: Style | None = None,
        transform: Transform | None = None,
        metadata: dict[str, Any] | None = None,
        primitive: dict | None = None,
    ) -> ElementNode:
        """Create and add an ElementNode without service-level graph mutation."""
        element = ElementNode(
            id=element_id,
            layer=layer,
            z_index=z_index,
            clip_to=clip_to,
            outline=normalize_outline(outline),
            constraints=constraints or CurveConstraints(),
            style=style or Style(),
            transform=transform or Transform(),
            metadata=metadata or {},
            primitive=primitive,
        )
        self.add_element(document_id, element)
        return element

    def create_rect(
        self,
        document_id: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        rx: float = 0.0,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        taper: float = 0.0,
        rotate: float = 0.0,
    ) -> ElementNode:
        """Create a rectangle, rounded rectangle, or tapered path element without committing."""
        rid = element_id or f"rect_{uuid.uuid4().hex[:6]}"
        max_rx = min(width, height) / 2
        rx_clamped = max(0.0, min(rx, max_rx))
        cx = x + width / 2
        top_w = width * (1.0 - max(-1.0, min(1.0, taper)))
        if abs(taper) > 0.001:
            top_x1 = cx - top_w / 2
            top_x2 = cx + top_w / 2
            outline = [
                (x, y + height),
                (x + width, y + height),
                (x + width, y),
                (top_x2, y),
                (cx, y - height * 0.08),
                (top_x1, y),
            ]
            primitive = None
            constraints = CurveConstraints(smoothness=0.35, closed=True)
        else:
            outline = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
            primitive = {"type": "rect", "x": x, "y": y, "width": width, "height": height, "rx": rx_clamped}
            constraints = CurveConstraints(smoothness=0.0, closed=True)
        element = self.create_element_node(
            document_id,
            element_id=rid,
            outline=outline,
            layer=layer,
            z_index=z_index,
            constraints=constraints,
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
                blend_mode=blend_mode,
            ),
            primitive=primitive,
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        return element

    def create_ellipse(
        self,
        document_id: str,
        *,
        cx: float,
        cy: float,
        rx: float,
        ry: float | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = "#CCCCCC",
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        rotate: float = 0.0,
    ) -> ElementNode:
        """Create an ellipse or circle element without committing."""
        rid = element_id or f"ellipse_{uuid.uuid4().hex[:6]}"
        ry_val = ry if ry is not None else rx
        if rx <= 0 or ry_val <= 0:
            raise ValueError("rx and ry must be positive")
        element = self.create_element_node(
            document_id,
            element_id=rid,
            outline=[(cx - rx, cy - ry_val), (cx + rx, cy + ry_val)],
            layer=layer,
            z_index=z_index,
            constraints=CurveConstraints(smoothness=0.0, closed=True),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
                blend_mode=blend_mode,
            ),
            primitive={"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry_val},
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        return element

    def create_line(
        self,
        document_id: str,
        *,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 1.0,
        y2: float = 1.0,
        points: list[list[float]] | None = None,
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        smoothness: float | None = None,
        rotate: float = 0.0,
    ) -> ElementNode:
        """Create a line, polyline, or open curve element without committing."""
        rid = element_id or f"line_{uuid.uuid4().hex[:6]}"
        if points is not None and len(points) < 2:
            raise ValueError("points must contain at least 2 coordinate pairs")
        if points is not None and len(points) > 2:
            outline = [(float(p[0]), float(p[1])) for p in points]
            primitive = None
            constraints = CurveConstraints(smoothness=smoothness if smoothness is not None else 0.35, closed=False)
        else:
            if points is not None:
                x1, y1 = float(points[0][0]), float(points[0][1])
                x2, y2 = float(points[1][0]), float(points[1][1])
            outline = [(x1, y1), (x2, y2)]
            primitive = {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}
            constraints = CurveConstraints(smoothness=0.0, closed=False)
        element = self.create_element_node(
            document_id,
            element_id=rid,
            outline=outline,
            layer=layer,
            z_index=z_index,
            constraints=constraints,
            style=Style(
                fill=None,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
                stroke_dasharray=stroke_dasharray,
            ),
            primitive=primitive,
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        return element

    def create_compound_path(
        self,
        document_id: str,
        *,
        subpaths: list[list[list[float]]],
        element_id: str | None = None,
        layer: str = "default",
        z_index: int = 0,
        fill: str | GradientDef | None = None,
        stroke: str | None = "#333333",
        stroke_width: float = 0.005,
        opacity: float = 1.0,
        blend_mode: str | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        smoothness: float = 0.0,
        closed: bool = False,
        rotate: float = 0.0,
    ) -> ElementNode:
        """Create one path containing multiple subpaths without committing."""
        rid = element_id or f"path_{uuid.uuid4().hex[:6]}"
        if len(subpaths) < 1:
            raise ValueError("compound_path requires at least one subpath")
        normalized_subpaths: list[list[Point2D]] = []
        outline: list[Point2D] = []
        for subpath in subpaths:
            if len(subpath) < 2:
                raise ValueError("Each compound_path subpath needs at least 2 points")
            pts = normalize_outline([(float(p[0]), float(p[1])) for p in subpath])
            normalized_subpaths.append(pts)
            outline.extend(pts)
        smooth = max(0.0, min(1.0, smoothness))
        element = self.create_element_node(
            document_id,
            element_id=rid,
            outline=outline,
            layer=layer,
            z_index=z_index,
            constraints=CurveConstraints(smoothness=smooth, closed=closed),
            style=Style(
                fill=fill,
                stroke=stroke,
                stroke_width=max(0.001, min(0.1, stroke_width)),
                opacity=max(0.0, min(1.0, opacity)),
                blend_mode=blend_mode,
                stroke_linecap=stroke_linecap,
                stroke_dasharray=stroke_dasharray,
            ),
            primitive={
                "type": "compound_path",
                "subpaths": normalized_subpaths,
                "closed": closed,
                "smoothness": smooth,
            },
        )
        if abs(rotate) > 0.001:
            object.__setattr__(element.transform, "rotate", rotate)
        return element

    def update_element(
        self,
        document_id: str,
        element_id: str,
        *,
        outline: list[Point2D] | None = None,
        smoothness: float | None = None,
        tensions: tuple[float, ...] | None = None,
        handle_in: tuple[tuple[float, float], ...] | None = None,
        handle_out: tuple[tuple[float, float], ...] | None = None,
        fill: str | GradientDef | None = None,
        stroke: str | None = None,
        stroke_width: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        clip_to: str | None = None,
        blend_mode: str | None = None,
        layer: str | None = None,
        metadata: dict[str, Any] | None = None,
        shape: dict | None = None,
        stroke_linecap: str | None = None,
        stroke_dasharray: str | None = None,
        blur: float | None = None,
    ) -> ElementNode:
        """Update an element's content/style fields without committing."""
        element = self.get_element(document_id, element_id)
        if shape is not None:
            self._apply_shape(element, shape)
        if outline is not None:
            element.outline = normalize_outline(outline)
        if smoothness is not None or tensions is not None or handle_in is not None or handle_out is not None:
            old_c = element.constraints
            element.constraints = CurveConstraints(
                smoothness=smoothness if smoothness is not None else old_c.smoothness,
                closed=old_c.closed,
                corner_style=old_c.corner_style,
                tensions=tensions if tensions is not None else old_c.tensions,
                handle_in=handle_in if handle_in is not None else old_c.handle_in,
                handle_out=handle_out if handle_out is not None else old_c.handle_out,
            )
        if (
            fill is not None
            or stroke is not None
            or stroke_width is not None
            or opacity is not None
            or blend_mode is not None
            or stroke_linecap is not None
            or stroke_dasharray is not None
            or blur is not None
        ):
            old_s = element.style
            element.style = Style(
                fill=fill if fill is not None else old_s.fill,
                stroke=stroke if stroke is not None else old_s.stroke,
                stroke_width=stroke_width if stroke_width is not None else old_s.stroke_width,
                opacity=opacity if opacity is not None else old_s.opacity,
                blend_mode=blend_mode if blend_mode is not None else old_s.blend_mode,
                stroke_linecap=stroke_linecap if stroke_linecap is not None else old_s.stroke_linecap,
                stroke_dasharray=stroke_dasharray if stroke_dasharray is not None else old_s.stroke_dasharray,
                blur=blur if blur is not None else old_s.blur,
            )
        if z_index is not None:
            element.z_index = z_index
        if clip_to is not None:
            element.clip_to = clip_to
        if layer is not None:
            element.layer = layer
        if metadata is not None:
            element.metadata.update(metadata)
        element.version += 1
        return element

    def delete_element(self, document_id: str, element_id: str) -> bool:
        elements = self.elements(document_id)
        if element_id not in elements:
            return False
        del elements[element_id]
        return True

    def delete_elements(self, document_id: str, ids: list[str]) -> list[str]:
        deleted: list[str] = []
        for element_id in ids:
            if self.delete_element(document_id, element_id):
                deleted.append(element_id)
        if deleted:
            self.commit(document_id, action="delete_elements", target=",".join(deleted))
        return deleted

    def group_elements(
        self,
        document_id: str,
        group_name: str,
        element_ids: list[str],
        *,
        replace: bool = False,
    ) -> list[str]:
        members = self.get(document_id).group_elements(group_name, element_ids, replace=replace)
        self.persist(document_id)
        return members

    def add_to_group(self, document_id: str, group_name: str, element_ids: list[str]) -> list[str]:
        members = self.get(document_id).add_to_group(group_name, element_ids)
        self.persist(document_id)
        return members

    def remove_from_group(self, document_id: str, group_name: str, element_ids: list[str]) -> list[str]:
        removed = self.get(document_id).remove_from_group(group_name, element_ids)
        self.persist(document_id)
        return removed

    def ungroup_elements(self, document_id: str, group_name: str | list[str]) -> bool | list[str]:
        removed = self.get(document_id).ungroup_elements(group_name)
        if removed:
            self.persist(document_id)
        return removed

    def get_group(self, document_id: str, group_name: str) -> list[dict]:
        return self.get(document_id).get_group(group_name)

    def list_groups(self, document_id: str) -> list[dict[str, int]]:
        return self.get(document_id).list_groups()

    def list_layers(self, document_id: str) -> list[dict[str, Any]]:
        return self.get(document_id).list_layers()

    def shift_layer_z(self, document_id: str, layer: str, z_offset: int) -> int:
        count = 0
        for element in self.elements(document_id).values():
            if element.layer == layer:
                element.z_index += z_offset
                element.version += 1
                count += 1
        if count:
            self.commit(document_id, action="shift_layer_z", target=layer)
        return count

    def touch(self, document_id: str) -> DocumentNode:
        doc = self.graph.get_document(document_id)
        doc.version += 1
        return doc

    def checkpoint(self, document_id: str, action: str, target: str | None = None) -> None:
        self.graph._auto_checkpoint(document_id, action, target or "")

    def persist(self, document_id: str) -> None:
        self.graph._persist(document_id)

    def commit(self, document_id: str, *, action: str | None = None, target: str | None = None) -> None:
        """Record one document mutation and persist the result."""
        self.touch(document_id)
        if action:
            self.checkpoint(document_id, action, target)
        self.persist(document_id)

    @staticmethod
    def _apply_shape(element: ElementNode, shape: dict) -> None:
        shape_type = shape.get("type")
        if shape_type == "rect":
            x, y = shape["x"], shape["y"]
            width, height = shape["width"], shape["height"]
            rx = shape.get("rx", 0.0)
            max_rx = min(width, height) / 2
            element.primitive = {
                "type": "rect",
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "rx": max(0.0, min(rx, max_rx)),
            }
            element.outline = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
            return
        if shape_type == "ellipse":
            cx, cy = shape["cx"], shape["cy"]
            rx = shape["rx"]
            ry = shape.get("ry", rx)
            if rx <= 0 or ry <= 0:
                raise ValueError("rx and ry must be positive")
            element.primitive = {"type": "ellipse", "cx": cx, "cy": cy, "rx": rx, "ry": ry}
            element.outline = [(cx - rx, cy - ry), (cx + rx, cy + ry)]
            return
        if shape_type == "line":
            x1, y1 = shape["x1"], shape["y1"]
            x2, y2 = shape["x2"], shape["y2"]
            element.primitive = {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2}
            element.outline = [(x1, y1), (x2, y2)]
            return
        raise ValueError(f"Unknown shape type: {shape_type}")
