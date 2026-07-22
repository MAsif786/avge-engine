"""
AVGE Engine — MCP server (controllers).

The primary LLM-facing interface. Registers MCP tools via controllers
and the skill guideline resources. Each controller module defines its
own tools — this file only wires them together.

§12.3: The M0b tools are registered as MCP tools, with input schemas
generated from the Tool Schema Registry (schemas/*.json) — single source
of truth, no duplicate schema maintenance.

The server advertises __tool_set_version__ so LLM clients can detect
stale cached tool lists after an engine upgrade.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from avge_engine import __version__, __tool_set_version__
from avge_engine.services.engine import (
    load_design_guidelines,
    load_environment_guidelines,
    load_tool_reference,
    SMOOTHNESS_GUIDANCE,
    TOOL_MAP,
)

# ── FastMCP server instance ───────────────────────────────────────

mcp = FastMCP(
    "AVGE Engine",
    instructions=f"""AI-Native Vector Graphics Engine (AVGE) — M0b Production Build.

Tool set version: {__tool_set_version__}

Coordinates are normalized 0.0–1.0 where (0,0) = top-left, (1,1) = bottom-right.

📏 **Proportion rule**: every object's canvas footprint must match its
real-world size. A desk is ~90%+ of canvas width; headphones on it are
~15–25%; a water bottle is ~6–8%. If an item sits on a surface, its
width should be ≤ ¼ of the supporting surface. See resource
avge://skill/design-guidelines Rule 5 for full guidance.

{SMOOTHNESS_GUIDANCE}

{TOOL_MAP}

🏙 **Environment scenes (see avge://skill/environment-guidelines):**
For streets, interiors, building exteriors, canals, bridges, and city scenes,
start with `create_perspective_grid`, block massing before detail, use
`create_facade_grid` for windows, and finish the first pass with
`apply_depth_haze`. Then run a densify pass: add overlapping buildings,
secondary signs/props, facade clutter, wires, and falloff-spaced poles.
Delete/hide all guide elements before final export.

📝 **Workflow — edit the same document, never rebuild from scratch:**
1. `create_document` once with a `name` for your scene.
2. `create_element` / `create_primitive` / `create_text` to add shapes.
3. `restyle` to recolor existing elements — no need to delete and recreate.
4. `describe_scene` / `render_preview` to check and iterate.
5. `checkpoint` before risky edits so `restore` can undo multiple steps.
6. `delete_element` to remove unwanted geometry — avoids full rebuilds.

🔄 **Multi-part objects (e.g. cups, books, characters):**
When an object has multiple elements (a cup body + handle + shadow, or a book
with cover + pages + spine), first `edit_group(action="create", group_name="...")`
to collect them under a name, then `transform_objects(group_name="...")` to
resize, reposition, or re-angle everything together.

👤 **Character design (see avge://skill/design-guidelines Rule 8):**
Before drawing any human character, first ask: what style (anime/realistic/cartoon/chibi)?
Each style has different head-to-body ratios, eye placement, and feature detail.
Build in order: face → hair → eyes → brows → nose → mouth → ears → neck + torso → arms → legs.
Use describe_scene between steps to verify positions. Checkpoint before risky edits.

⚡ **Batch patterns (execute ALL tools in one call):**
  batch(ops=[{{"tool":"create_element", ...}}, {{"tool":"restyle", ...}}])
  💡 Create + style in one call instead of two.
""",
)


# ── MCP Resource: full design guidelines ──────────────────────────

@mcp.resource(
    uri="avge://skill/design-guidelines",
    name="AVGE Design Guidelines",
    description="Full design skill: aesthetic conventions for two-tone shading, "
    "stroke-weight hierarchy, palette selection, grounding, composition, "
    "and style-register matching. Referenced by tool descriptions.",
    mime_type="text/markdown",
)
async def design_guidelines_resource() -> str:
    """Return the full design guidelines markdown document."""
    return load_design_guidelines()


@mcp.resource(
    uri="avge://skill/environment-guidelines",
    name="AVGE Environment Guidelines",
    description="Full environment skill: perspective construction, building massing, "
    "facade/window density, signage perspective, atmospheric haze, "
    "and QA flow for street, interior, and architecture scenes.",
    mime_type="text/markdown",
)
async def environment_guidelines_resource() -> str:
    """Return the full environment guidelines markdown document."""
    return load_environment_guidelines()


@mcp.resource(
    uri="avge://tool-reference",
    name="AVGE Tool Reference",
    description="Full per-tool reference: all 55 tools, params, modes, examples, "
    "and the complete generate_shape pattern table with 19 patterns.",
    mime_type="text/markdown",
)
async def tool_reference_resource() -> str:
    """Return the full tool reference markdown document."""
    return load_tool_reference()


# ── Register controllers ──────────────────────────────────────────

from avge_engine.controllers import register_all  # noqa: E402

register_all(mcp)


# ── Entry points ──────────────────────────────────────────────────


def run_stdio() -> None:
    """Run MCP server via stdio transport."""
    mcp.run(transport="stdio")


def run_sse(host: str = "0.0.0.0", port: int = 8001) -> None:
    """Run MCP server via SSE transport (HTTP)."""
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.run(transport="sse")


def run_streamable_http(host: str = "0.0.0.0", port: int = 8002) -> None:
    """Run MCP server via Streamable HTTP transport (Antigravity-compatible)."""
    mcp.settings.host = host
    mcp.settings.port = port
    # Antigravity expects the MCP endpoint at the path specified in serverUrl
    mcp.settings.streamable_http_path = "/mcp"
    mcp.run(transport="streamable-http")
