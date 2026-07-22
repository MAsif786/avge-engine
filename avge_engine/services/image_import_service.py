"""Image and SVG import helpers for element tools."""
from __future__ import annotations

import base64
import mimetypes
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_EMBED_BYTES = 2_000_000
MAX_SVG_IMPORT_BYTES = 1_000_000


def read_href_bytes(href: str, max_bytes: int = MAX_EMBED_BYTES) -> tuple[bytes, str]:
    """Read bytes from http(s), file path, or data URI with a hard size cap."""
    if href.startswith("data:"):
        header, _, payload = href.partition(",")
        if not payload:
            raise ValueError("Invalid data URI")
        raw = base64.b64decode(payload) if ";base64" in header else payload.encode("utf-8")
        mime = header[5:].split(";")[0] or "application/octet-stream"
        if len(raw) > max_bytes:
            raise ValueError(f"Image too large ({len(raw)} bytes, max {max_bytes})")
        return raw, mime

    parsed = urlparse(href)
    if parsed.scheme in ("http", "https"):
        req = Request(href, headers={"User-Agent": "AVGE/0.5"})
        with urlopen(req, timeout=10) as response:
            mime = response.headers.get_content_type() or "application/octet-stream"
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"Image too large (max {max_bytes} bytes)")
        return raw, mime
    if parsed.scheme and parsed.scheme != "file":
        raise ValueError("Only http, https, file, local path, and data URI hrefs are supported")

    path = Path(parsed.path if parsed.scheme == "file" else href).expanduser()
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError(f"Image too large ({len(raw)} bytes, max {max_bytes})")
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return raw, mime


def bytes_to_data_uri(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def is_svg_href(href: str, mime: str | None = None) -> bool:
    if mime == "image/svg+xml":
        return True
    clean = href.split("?", 1)[0].lower()
    return clean.endswith(".svg") or href.startswith("data:image/svg+xml")


def svg_path_elements(
    svg_text: str,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    fill_override: str | None,
    stroke_override: str | None,
    stroke_width: float,
    samples_per_curve: int,
    max_paths: int,
) -> list[dict[str, Any]]:
    """Parse SVG path elements into mapped element definitions."""
    from avge_engine.geometry.procedural import parse_svg_path

    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid SVG: {exc}") from exc

    view_box = _svg_viewbox(root)
    elements: list[dict[str, Any]] = []
    for path_node in root.iter():
        if path_node.tag.rsplit("}", 1)[-1] != "path":
            continue
        path_data = path_node.attrib.get("d")
        if not path_data:
            continue
        outline = parse_svg_path(path_data, samples_per_curve=samples_per_curve)
        if len(outline) < 2:
            continue
        mapped = _map_svg_outline(outline, view_box, x, y, width, height)
        fill = fill_override if fill_override is not None else path_node.attrib.get("fill", "#CCCCCC")
        stroke = stroke_override if stroke_override is not None else path_node.attrib.get("stroke", "#333333")
        if fill in ("none", "transparent"):
            fill = None
        if stroke in ("none", "transparent"):
            stroke = None
        elements.append({"outline": mapped, "fill": fill, "stroke": stroke, "stroke_width": stroke_width})
        if len(elements) >= max_paths:
            break
    return elements


def _parse_svg_length(value: str | None) -> float | None:
    if not value:
        return None
    match = re.match(r"\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)", value)
    return float(match.group(1)) if match else None


def _svg_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    view_box = root.attrib.get("viewBox")
    if view_box:
        nums = [float(v) for v in re.findall(r"[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?", view_box)]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            return nums[0], nums[1], nums[2], nums[3]
    width = _parse_svg_length(root.attrib.get("width")) or 1.0
    height = _parse_svg_length(root.attrib.get("height")) or 1.0
    return 0.0, 0.0, max(0.001, width), max(0.001, height)


def _map_svg_outline(
    outline: list[tuple[float, float]],
    view_box: tuple[float, float, float, float],
    x: float,
    y: float,
    width: float,
    height: float,
) -> list[tuple[float, float]]:
    vb_x, vb_y, vb_w, vb_h = view_box
    return [
        (x + ((px - vb_x) / vb_w) * width, y + ((py - vb_y) / vb_h) * height)
        for px, py in outline
    ]
