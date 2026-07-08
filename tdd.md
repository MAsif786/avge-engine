# Technical Design Document (TDD)
## AI-Native Vector Graphics Engine (AVGE)

**Version:** 0.5 (M0b — built)
**Status:** Design
**Companion to:** AVGE PRD v0.1 · **AVGE MVP TDD v0.1** (validation-spike companion document)
**Owner:** Engine Team
**Changelog:**
- v0.2 resolved 8 review findings from v0.1 (coordinate system, text/image tools, determinism edge cases, metadata query boundary, animation scope, large-document query cost, operational basics, output-quality metrics) and added a Technology Stack section.
- v0.3 replaced the Rust-first stack with a **Python-first v0** stack (§12.1) plus explicit, measurable triggers for extracting numerically-sensitive engines to a compiled language later (§12.2). Determinism requirements (§8) unchanged. Committed to **MCP** as the primary tool-call transport (§12, §12.3).
- v0.4 (round-2 review) resolves: Guide object type had no tool (§4.5b, same gap pattern Text/Image had in v0.1); no practical outline-size guidance beyond the hard abuse limit (§4.5c); `boolean_operation`/`duplicate_region` metadata handling was undefined (§6.4); MCP schema versioning didn't address a live session mid-conversation (§12.3); and — most importantly — adds a **formal, hard validation gate (M0a)** before any further build, spun out into a separate, deliberately minimal **companion MVP TDD** rather than folded into this production design.

---

## 1. Purpose & Scope

This TDD translates the AVGE PRD into an implementable system design. It defines the object model, the public tool API contract, the internal engine pipeline, data structures, determinism guarantees, and the execution/rendering loop that lets an LLM drive a vector graphics engine through JSON tool calls only.

**In scope:** engine architecture, scene graph schema, tool API contracts, geometry/curve/effects/render/export pipeline, batch execution, animation system, persistence (checkpoint/restore), determinism strategy, performance targets, technology stack.

**Out of scope:** any semantic/artistic reasoning (owned entirely by the LLM), specific LLM prompting strategy, UI/editor chrome, multi-user real-time collaboration (future work), skeletal/IK character rigging (explicitly descoped — see §10.1).

---

## 2. Design Goals (from PRD → engineering requirements)

| PRD Principle | Engineering Requirement |
|---|---|
| Engine has no semantic understanding | No object type, tool, or internal module may reference semantic labels (e.g. "eye", "wall"). Metadata is opaque string key/value storage only. Query tools may match metadata by **equality/containment only** — see §5.6 for the precise boundary. |
| LLM owns intelligence | Engine exposes *inspection* primitives (`describe_*`, `render_*`) rich enough that the LLM never needs engine-side inference to "see" its work. |
| No SVG/Bézier authoring by LLM | LLM outlines are coarse polylines/point arrays; all curve fitting, smoothing, and optimization happen server-side. |
| Deterministic | Given identical input JSON + engine version, output geometry/SVG must be byte-identical. No RNG in any code path reachable from tool calls. See §8 for how known non-deterministic algorithm classes are constrained. |
| ≤ 20–25 public tools | Public API surface is versioned and enforced via a schema registry; internal ops are unlimited but never exposed. |
| JSON-only I/O | Every tool call and every tool response is JSON; no free text, no XML fragments returned to the LLM. |
| Batchable | All mutating tools accept either a single op or an array of ops in one call; internal dispatcher fans out. |

---

## 3. System Architecture

### 3.1 High-Level Component Diagram

```
┌─────────────┐
│     LLM      │  (external — GPT/Claude/Gemini)
└──────┬──────┘
       │ JSON tool calls
┌──────▼──────────────┐
│   Tool Gateway        │  validation, auth, rate limit, schema check, quota guard
└──────┬──────────────┘
┌──────▼──────────────┐
│  Command Dispatcher   │  routes batched ops, transaction boundary
└──────┬──────────────┘
┌──────▼──────────────┐
│   Scene Graph Store    │  in-memory + persisted document state
└──────┬──────────────┘
       ├────────────┬─────────────┬──────────────┐
┌──────▼───┐  ┌──────▼───┐  ┌──────▼───┐  ┌───────▼──────┐
│ Geometry  │  │  Curve    │  │ Effects  │  │  Animation    │
│  Engine   │  │  Engine   │  │  Engine  │  │  Engine       │
└──────┬───┘  └──────┬───┘  └──────┬───┘  └───────┬──────┘
       └────────────┴─────────────┴──────────────┘
                      │
              ┌───────▼────────┐
              │    Renderer      │  rasterizer + SVG serializer
              └───────┬────────┘
              ┌───────▼────────┐
              │    Exporter      │  SVG / PDF / Canvas / Animation
              └─────────────────┘
```

### 3.2 Process Model

- **Stateless Tool Gateway**: horizontally scalable, holds no document state. Also owns input-size quota checks (§9.4) before any op reaches the dispatcher.
- **Stateful Scene Graph Store**: one instance (or shard) per document session, addressed by `document_id`. Backed by an append-only operation log for checkpoint/restore.
- **Engines are pure functions**: Geometry, Curve, Effects, and Animation engines take `(SceneGraph, Op) → SceneGraphDelta`. No hidden state, no I/O, no wall-clock reads, no randomness — this is what makes determinism enforceable and testable.

---

## 4. Scene Graph Data Model

### 4.1 Node Types

```
Document
 └─ Layer[]
     └─ Group[]
         └─ Region | Text | Image | Guide
     └─ Animation[]
```

### 4.2 Coordinate System & Document Definition *(resolves review #2)*

Previously undefined — now specified explicitly:

- `create_document` **must** take an explicit canvas size: `{ "width": 1000, "height": 1000, "unit": "px" }`. There is no implicit/default canvas.
- All object coordinates (`outline`, `transform.translate`, etc.) are expressed in a **normalized unit space, 0.0–1.0 on both axes**, where `(0,0)` is the top-left of the canvas and `(1,1)` is the bottom-right. This keeps tool input resolution-independent for the LLM.
- The engine maps normalized coordinates to the document's actual `width`/`height` (in the declared `unit`, default `px`) only at render/export time.
- Stroke width, font size, and effect parameters (blur radius, shadow offset) are expressed in the **same normalized space as a fraction of the canvas's shorter dimension**, not in absolute px — this keeps a "0.01 stroke" visually consistent whether the canvas is 200px or 4000px. `describe_object` returns both the normalized value and the resolved absolute value (in the document's declared unit) for LLM convenience.
- Rotation is degrees, clockwise-positive, about the object's local bounding-box center unless a `pivot` is explicitly supplied.

### 4.3 Core Schema (canonical internal representation)

```json
{
  "id": "string (uuid)",
  "type": "document | layer | group | region | text | image | guide",
  "parent": "id | null",
  "transform": {
    "translate": [0, 0],
    "rotate": 0,
    "scale": [1, 1],
    "skew": [0, 0],
    "pivot": [0.5, 0.5]
  },
  "style": {
    "fill": "#RRGGBB | gradient_ref | null",
    "stroke": { "color": "#RRGGBB", "width": 0.01 },
    "opacity": 1.0,
    "effects": []
  },
  "geometry": {
    "outline": [[x, y], ...],
    "curve_fit": { "smoothness": 0.5, "closed": true }
  },
  "metadata": { "tags": ["string"], "custom": {} },
  "version": 1
}
```

Key design decision: **`metadata` is the only place semantic information may live**, and it is stored as opaque strings. No engine code path branches rendering, geometry, or animation behavior on `metadata` contents — enforced by a lint rule (§11.2).

### 4.4 Region Primitive (core object)

A Region is defined by:
- **outline**: an ordered list of coarse points supplied by the LLM (polyline or point cloud), in normalized coordinates (§4.2).
- **curve_fit parameters**: smoothness, symmetry, corner style, closed/open, winding — geometric constraints only (PRD §16).
- **derived geometry**: engine-computed optimized Bézier path, cached and versioned.

The LLM never sees or edits the derived Bézier path directly; it only sees the coarse outline it submitted and query results (bounds, area, curvature) describing the derived shape.

### 4.5 Text and Image Objects *(resolves review #3)*

`Text` and `Image` were declared as object types in the PRD's object model but had no corresponding tools. Resolved as follows — both are handled by the existing `create_region`/`edit_region` tools via a `type` discriminator, rather than adding new top-level tools (keeps the public tool count down):

**Text:**
```json
{
  "tool": "create_region",
  "type": "text",
  "id": "label_1",
  "content": "Hello",
  "position": [0.5, 0.1],
  "font": { "family": "Inter", "size": 0.04, "weight": 400 },
  "align": "center",
  "style": { "fill": "#000000" }
}
```
Text has no LLM-supplied `outline` — the engine computes its own bounding geometry from `content` + `font` + a fixed, versioned font-metrics table (deterministic; no OS/browser font-fallback ambiguity — the engine ships/embeds its own font set, see §12 Tech Stack). `describe_object` on a text node returns resolved bounds like any other object.

**Image:**
```json
{
  "tool": "create_region",
  "type": "image",
  "id": "img_1",
  "source": "asset_ref_or_base64",
  "position": [0.1, 0.1],
  "size": [0.3, 0.3],
  "fit": "contain | cover | stretch"
}
```
Images are treated as an opaque raster payload placed and transformed like any region (crop/clip via `boolean_operation` against a mask region is supported); the engine does not interpret image contents.

Both share the full Transform, Style (where applicable), Query, and Animation tool surface — no new public tools are added, keeping the total at 21 (§5.1).

### 4.5b Guide Objects *(resolves review round 2, #1)*

`Guide` was declared as a node type (§4.1) with no corresponding tool — same gap Text/Image had. Resolved the same way: via `create_region` with `type: "guide"`.

```json
{
  "tool": "create_region",
  "type": "guide",
  "id": "guide_1",
  "orientation": "horizontal | vertical",
  "position": 0.5
}
```

Guides are non-rendering, non-exporting reference lines used purely for the LLM's own alignment reasoning (e.g. "place these objects symmetric about this guide"). They appear in `describe_scene`/`describe_object` output like any object (so the LLM can query positions relative to them) but are excluded from `render`/`export` output by default; an explicit `include_guides: true` flag on `export` overrides this for debugging.

### 4.5c Practical Outline Size Guidance *(resolves review round 2, #2)*

§9.4 caps `outline` at 2,000 points as a hard abuse guard — but that number is not a usability target. An LLM reasoning about shape in raw coordinate arrays is doing better spatial reasoning with a small, deliberate point set than a large one:

- **Recommended range for LLM-authored outlines: 3–30 points.** The Curve Engine's `smoothness`/`corner_style` constraints (§4.4, PRD §16) exist specifically so a simple, coarse polygon can still produce a refined-looking curve — the LLM should lean on constraints rather than on point density to get quality.
- The Tool Gateway does not reject outlines above this range (only above the hard 2,000-point limit), but `create_region`'s response includes an advisory (non-blocking) warning like `"warnings": ["outline has 180 points; consider fewer points + smoothness constraints for better curve quality"]` when point count is high relative to the shape's bounding-box complexity, to nudge the LLM back toward the intended usage pattern without hard-blocking edge cases that genuinely need more points (e.g. detailed traced outlines from a reference image).
- This guidance should be validated (not just asserted) during the MVP evaluation — see the companion MVP TDD.

### 4.5d Smoothness Guidance (empirically validated in MVP spike)

The MVP spike (§MVP TDD) ran all 5 benchmark prompts through both visual and text-only feedback loops, producing the following empirical mapping between subject type and optimal `smoothness`:

| Shape category | Example | Recommended smoothness | Rationale |
|---|---|---|---|
| **Geometric / polygonal** | House icon walls, star, rectangles, doors, windows | **0.0–0.1** | Sharp corners preserve the intended angular form; any smoothing rounds edges the LLM explicitly placed as corners. |
| **Mixed rigid/organic** | Coffee cup body, tree trunk, saucer | **0.2–0.5** | Slight softening prevents jaggedness from coarse point outlines while keeping the structural lines crisp. |
| **Organic / curved** | Tree foliage, smiley face circle, cup rim | **0.6–0.8** | High smoothness produces the natural, flowing curves expected of these subjects; the LLM can use coarse (~4–8 point) outlines and let the engine fill in the arc quality. |
| **Deliberately sharp with smooth sub-elements** | Smiley face (face=0.8, eyes=0.8, mouth=0.8 open curve) | Mixed per-region | A single scene mixes smoothness values per region — not a single global value. The LLM assigns per-region smoothness, which the engine accepts without normalization or smoothing across regions. |

**Key finding from MVP validation:** without this guidance, an LLM with no vector-graphics experience defaults to `smoothness=0.5` (the tool's default) for everything. In the spike, this produced:
- A five-pointed star that was visibly blobby at `smoothness=0.3` (first attempt, text-only mode) versus perfectly sharp at `smoothness=0.0` (second attempt after describe_scene feedback).
- Tree foliage that benefited from `smoothness=0.6–0.7` across all 4 foliage regions — the LLM correctly assigned higher smoothness to organic shapes without explicit guidance, but only after seeing `render_preview` results.

This table should be added to the LLM's **system prompt** alongside tool definitions (or as a tool-injection preamble in the MCP server's `instructions` field), so the LLM has a default strategy per subject type rather than rediscovering it per prompt. The Tool Gateway's advisory warning (§4.5c) should also add per-region guidance when `smoothness` appears mismatched to outline complexity — e.g. a high-point-count outline with `smoothness=0.0` gets a warning like `"warnings": ["outline with 40+ points and smoothness=0.0: many points + sharp corners may produce jagged output; consider increasing smoothness or reducing point count"]`.

### 4.6 Versioning & Immutability

Every node carries a monotonically increasing `version`. Mutations produce a new version rather than mutating in place, enabling:
- Deterministic replay from the operation log.
- Cheap `checkpoint`/`restore` (snapshot = document id + version vector).
- Conflict-free batch application (ops within a batch apply against a consistent snapshot).

### 4.7 Deletion Semantics *(resolves review #7, part 1)*

- Deleting a **Group or Layer cascades** to all descendants by default (`delete_region`/future `delete_group` remove the full subtree).
- An explicit `{ "orphan_children": true }` flag reparents children to the deleted node's parent instead of deleting them, for cases where the LLM wants to dissolve a grouping without losing content.
- Deleting a node referenced by an active `Animation` group invalidates that animation's target; `animate`/`export_animation` return a structured warning (not a hard failure) listing dropped targets.

---

## 5. Public Tool API

### 5.1 Tool Inventory (target: ≤ 25)

| Category | Tools |
|---|---|
| Document | `create_document`, `render`, `export` |
| Geometry | `create_region`, `edit_region`, `delete_region`, `duplicate_region`, `group_regions` |
| Transform | `transform_objects` |
| Style | `style_objects` |
| Boolean | `boolean_operation` |
| Query | `describe_scene`, `describe_object`, `render_preview`, `render_objects`, `find_objects` |
| Animation | `prepare_animation`, `animate`, `export_animation` |
| Utility | `batch`, `checkpoint`, `restore` |

**Total: 21 tools.** Text and Image are handled via `type` discriminators on the geometry tools (§4.5), not additional tools.

### 5.2 Contract Conventions

- Every tool has a JSON Schema (request + response) registered in a **Tool Schema Registry**, versioned independently of engine internals.
- Every mutating tool returns: `{ "status": "ok|error", "affected_ids": [...], "warnings": [...], "version": n }`.
- Every mutating tool accepts an optional `constraints` object (geometric only — see PRD §16).
- No tool response ever contains SVG/XML markup or prose; `render_preview` returns either a structured description or a reference (e.g. `preview_url` / base64 raster), never inline vector markup for the LLM to parse as text.

### 5.3 Example: `create_document`

```json
{
  "tool": "create_document",
  "width": 1000,
  "height": 1000,
  "unit": "px",
  "background": "#FFFFFF"
}
```

### 5.4 Example: `create_region`

Request:
```json
{
  "tool": "create_region",
  "id": "object_1",
  "layer": "layer_1",
  "outline": [[0.1,0.2],[0.8,0.2],[0.9,0.7],[0.2,0.8]],
  "constraints": { "closed": true, "smoothness": 0.4 },
  "style": { "fill": "#E8E8E8" },
  "metadata": { "tags": ["foreground"] }
}
```

Response:
```json
{
  "status": "ok",
  "affected_ids": ["object_1"],
  "bounds": { "x": 0.1, "y": 0.2, "w": 0.8, "h": 0.6 },
  "warnings": [],
  "version": 1
}
```

### 5.5 Example: `batch`

```json
{
  "tool": "batch",
  "ops": [
    { "tool": "create_region", "id": "r1", "outline": [...] },
    { "tool": "create_region", "id": "r2", "outline": [...] },
    { "tool": "style_objects", "ids": ["r1", "r2"], "style": { "fill": "#000" } }
  ],
  "atomic": true
}
```

- `atomic: true` → all-or-nothing transaction against a single snapshot; on any op failure the whole batch rolls back and returns a single error with the failing op index.
- `atomic: false` → best-effort; per-op results returned in an array, matching the PRD's "40 creations → 1 call → 1 response" pattern (PRD §11).
- Batch size is capped — see §9.4.

### 5.6 `find_objects` — the metadata query boundary *(resolves review #1)*

The PRD states the engine "stores tags, never interprets them" but didn't define what a query tool is allowed to do with them. Explicit rule:

- `find_objects` may filter/match on metadata using **equality, containment (`tag in [...]`), and numeric/geometric comparisons** (e.g. `bounds.area > 0.1`, `tags contains "foreground"`).
- `find_objects` (or any other tool) may **never** apply conditional *behavior* based on metadata content — e.g. no "if tag looks like a body part, adjust animation blending." Matching is symbol-level string/number comparison; the engine assigns no meaning to *which* string matched.
- This distinction is enforced by the semantic-leak lint (§11.2): matching code may call `metadata.tags.includes(x)` where `x` is a caller-supplied value; it may never contain a literal semantic string (e.g. `"eye"`, `"wall"`) inside engine source code itself.

### 5.7 Describe APIs (the LLM's "eyes")

`describe_scene()` returns: object list, bounds, groups, layer count, complexity score, empty-space regions, warnings (e.g. overlapping regions, off-canvas objects).

`describe_object(id)` returns: bounds, area, perimeter, curvature samples, neighbor ids (spatial proximity), style, transform, metadata, current version.

**Large-document pagination** *(resolves review #6)*: `describe_scene` accepts optional `{ "cursor": "...", "limit": 100, "filter": {...}, "detail": "summary|full" }`.
- `detail: "summary"` (default) returns id, type, bounds, and top-level tags only — no curvature/neighbor data — keeping the response compact for large scenes.
- `detail: "full"` returns the complete per-object payload but only for the page requested (`limit`, default 100, max 500).
- Response includes `total_count` and `next_cursor` so the LLM can decide whether to page further or narrow with `find_objects` first. This keeps a 500-region document from blowing a single tool response past a reasonable token budget.

### 5.8 Rendering APIs

`render_preview()`, `render_objects()` — return a raster reference (URL or size-capped base64 PNG) at a bounded default resolution (e.g. 1024px longest edge), with an optional `resolution` override capped at a max to bound response size and render cost.

---

## 6. Internal Engine Pipeline

### 6.1 Geometry Engine
- Validates and normalizes outlines (dedupes points, resolves self-intersections per a documented policy, canonicalizes winding order).
- Computes bounds, area, centroid — pure geometric math, cached per version.

### 6.2 Curve Engine
- Fits Bézier curves to the coarse outline using the supplied constraints (smoothness, symmetry, corner style).
- See §8.1 for how fitting is kept deterministic.

### 6.3 Effects Engine
- Applies fill, stroke, gradients, opacity, filters (blur, shadow) as a declarative style→render transform. Effects are composable and order-preserving (array order = paint order).

### 6.4 Boolean Engine
- Union / subtract / intersect / xor over closed regions, implemented on the derived Bézier/polygon representation.
- **Style conflict resolution**: the resulting region's style is taken from the first (lowest-index) input by default; an optional `result_style` parameter lets the caller specify fill/stroke explicitly instead of relying on the default. This is documented behavior, not an unspecified merge.
- **Metadata handling** *(resolves review round 2, #3)*: the original §6.4 design resolved style conflicts but left metadata undefined — since metadata is the LLM's only semantic memory of what an object represents, this matters as much as style. Rule: the resulting region's `metadata.tags` is the **union** of all input regions' tags (deduplicated); `metadata.custom` follows the same first-input-wins default as style, overridable via an optional `result_metadata` parameter. `duplicate_region` copies metadata verbatim by default (the LLM is expected to update tags on the copy if the duplicate now means something different — the engine doesn't guess).
- Output is a new Region with fresh derived geometry; inputs are either deleted or retained per an explicit `keep_originals` flag.
- See §8.2 for determinism handling of clipping edge cases.

### 6.5 Animation Engine
- Operates on **Groups only**, never on individual sub-parts implicitly (PRD §17) — an animation op targets a group id and a set of transform keyframes.
- Scope is explicitly **transform + opacity interpolation only**: translate, rotate, scale, skew, opacity, over time, with standard easing curves. **No skeletal rigging, inverse kinematics, or per-vertex/mesh deformation** — see §10.1 for why this descopes part of the PRD's "character animation" future-module claim.
- `prepare_animation`: validates target groups exist and are animatable, returns a timeline handle.
- `animate`: appends keyframes.
- `export_animation`: bakes keyframes to the requested format (SVG SMIL/CSS, or frame-sequence for video export).

### 6.6 Renderer
- Deterministic rasterizer + SVG serializer. Given a scene graph snapshot, produces identical bytes every time (fixed float precision/rounding, fixed attribute ordering, fixed namespace declarations).

### 6.7 Exporter
- Wraps Renderer output into target containers: SVG file, PDF (via a deterministic SVG→PDF path), flattened Canvas/PNG raster, or animation package.

---

## 7. Undo/Redo Model *(resolves review #7, part 3)*

Beyond raw `checkpoint`/`restore` (explicit named snapshots), the operation log itself provides implicit linear undo:

- Every applied op (or atomic batch) is one entry in the append-only log with a monotonic sequence number.
- An `undo_last()` internal capability (exposed publicly as `restore` with an implicit "previous version" checkpoint if no explicit checkpoint was taken) rolls the document's live pointer back one log entry.
- Branching (undo then apply a different op) does not delete the abandoned log entries — they remain for audit/debugging but are excluded from the live document's ancestry. Garbage collection of orphaned branches is a storage-layer concern, not a public API concern, and is out of scope for v0.2.

---

## 8. Determinism Strategy *(expanded — resolves review #4)*

Determinism is a hard requirement, not just an aspiration, so the two algorithm classes most likely to violate it are called out explicitly with mitigations:

### 8.1 Curve Fitting Determinism
Risk: iterative/optimization-based curve fitting can be sensitive to floating-point rounding and platform differences in convergence order.
Mitigation:
- Use a **closed-form, non-iterative fitting method** as the default (e.g. Catmull-Rom-to-cubic-Bézier conversion, or least-squares fit solved via a fixed direct linear solve rather than gradient descent).
- If an iterative refinement pass is used for high-smoothness requests, it runs a **fixed, non-adaptive iteration count** (no early-exit-on-tolerance, since tolerance-based exit is a common non-determinism source) and a **fixed floating-point evaluation order**.
- All floating-point math in the Curve Engine uses IEEE-754 double precision uniformly across environments (no mixed 32/64-bit paths, no SIMD paths that reorder summation unless bit-reproducibility is verified).

### 8.2 Boolean/Clipping Determinism
Risk: polygon clipping algorithms have known edge cases (touching edges, near-duplicate vertices, degenerate zero-area slivers) where different implementations — or even the same implementation with different input ordering — can disagree.
Mitigation:
- Curves are flattened to line segments at a **fixed tolerance constant** before clipping (never an adaptive/resolution-dependent tolerance).
- Input point ordering is canonicalized (consistent winding, consistent starting vertex selection) before the clip algorithm runs, so equivalent-but-differently-ordered inputs still produce identical output.
- Degenerate/near-zero-area results are snapped to a documented minimum-area threshold rather than left to float noise.
- The chosen clipping library/algorithm is pinned by exact version; upgrades go through the golden regression suite (§11.3) before rollout.

### 8.3 General Rules (unchanged from v0.1, retained)
1. No wall-clock, no RNG, no thread-race-dependent ordering anywhere in the engine pipeline or dispatcher.
2. Fixed floating-point rounding (round to 6 decimal places) applied at every serialization boundary.
3. Stable ordering: object arrays always ordered by creation order / explicit z-index, never by hash-map iteration order.
4. Golden-output regression tests: fixed input corpus → byte-for-byte SVG output checked on every engine build.
5. Engine version pinning: each document snapshot records the engine version that produced it; replay uses that exact version.

---

## 9. Performance, Limits & Abuse Guards

### 9.1 Performance Targets

| Operation | Target (p95) |
|---|---|
| `create_region` (single) | < 50ms |
| `batch` (40 ops) | < 400ms |
| `describe_scene` (summary, ≤100 objects) | < 150ms |
| `render_preview` (raster, 1024px) | < 300ms |
| `boolean_operation` (2 regions, < 500 points) | < 100ms |
| `export` (SVG, typical document) | < 500ms |

### 9.4 Input Size & Abuse Guards *(resolves review #7, part 4)*

An LLM-facing API must guard against pathological-but-plausible inputs (accidental, not just malicious) at the Tool Gateway, before any op reaches the dispatcher:

| Limit | Value (default) |
|---|---|
| Max points per `outline` | 2,000 |
| Max ops per `batch` call | 200 |
| Max objects per document | 10,000 |
| Max `metadata.custom` size per node | 4 KB |
| Max nesting depth (Layer→Group→...) | 16 |
| Max image payload (base64 inline) | 5 MB (larger via asset reference/upload only) |

Requests exceeding a limit return a structured `status: "error"` with `error_code: "limit_exceeded"` and the specific limit — never a silent truncation, which would produce surprising geometry.

---

## 10. Extensibility (PRD §18/§21)

- New "modules" (logo design, icons, infographics, floor plans, UI assets) must be built as **higher-level compositions of existing public tools plus richer metadata conventions**, not as new engine primitives or semantic-aware code paths.
- If a genuinely new geometric capability is needed (e.g. a new boolean mode), it is added as an internal op first, exposed publicly only if it fits within the ≤25 tool budget — otherwise folded into an existing tool via a parameter.

### 10.1 Character Animation — Scope Correction *(resolves review #5)*

The PRD lists "character animation" as a future module requiring "no engine changes." As designed, the Animation Engine (§6.5) supports only group-level transform/opacity interpolation — sufficient for rigid-body animation (a logo sliding/rotating, icons pulsing, simple walk-cycles built from independently-transformed limb groups swapped frame-to-frame) but **not** for smooth skeletal deformation, inverse kinematics, or per-vertex mesh warping that "character animation" usually implies.

Two honest paths forward, to be decided before this module is prioritized:
1. **Scope character animation down** to "puppet-style" animation — rigid groups (limbs, head, torso) animated independently, like a paper cutout puppet — which *does* fit the existing engine unchanged.
2. **Add a genuinely new capability** (bone hierarchies + weighted deformation) as a dedicated design effort with its own TDD, acknowledging this contradicts the PRD's "no engine changes required" claim.

This TDD assumes path 1 for v1; path 2 is out of scope until explicitly greenlit.

---

## 11. Quality, Testing & Guardrails

### 11.1 Schema Validation
All tool calls validated against the Tool Schema Registry before reaching the dispatcher; malformed calls return structured errors, never partial mutation.

### 11.2 Semantic-Leak Lint
Static analysis rule that fails CI if any file outside `metadata` serialization/query code contains a literal semantic string, or if any non-query code path reads `metadata.tags`/`metadata.custom` for branching logic — enforces PRD Principle 1 and the §5.6 query boundary at the codebase level, not just by convention.

### 11.3 Golden Regression Suite
Fixed corpus of documents + op sequences → expected byte-identical SVG/PDF output, run on every commit. Includes dedicated cases for the curve-fitting and boolean-clipping edge cases identified in §8.1/§8.2.

### 11.4 Fuzz & Property Tests
- Property: `boolean_operation` output area ≈ expected set-theoretic area within tolerance.
- Property: `restore(checkpoint)` always yields a scene graph equal to the one at checkpoint time.
- Property: two calls to `create_region` with the same input (any point ordering that represents the same polygon) yield the same derived geometry.
- Fuzz: random (but seeded, reproducible) outlines through the Curve Engine must never crash and must always return closed, non-self-intersecting output when `closed: true`.

### 11.5 Load/Latency Tests
Batch sizes from 1–200 ops benchmarked against §9.1 targets; regression alerts on p95 drift > 20%.

### 11.6 Output Quality Metrics *(resolves review #8)*

§20 of the PRD measures only tool-call efficiency and engine cleanliness — nothing about whether output actually matches intent. Added metrics:

| Metric | Definition | Target |
|---|---|---|
| Outline fidelity | Hausdorff distance between LLM's coarse outline and the final fitted curve, normalized to canvas size | < 0.02 at default smoothness |
| Preview-round-trip accuracy | Human/LLM-rated match between `describe_scene` output and an independent visual inspection of `render_preview`, sampled periodically | ≥ 95% agreement |
| Revision efficiency | Median number of `batch` + `describe_*` round trips to reach a human-accepted final design, across a benchmark task set | tracked trend, target: decreasing over releases |
| Export fidelity | Visual diff (pixel or structural) between `render_preview` and final exported file | zero visible diff at target resolution |

These are evaluated against a fixed benchmark task set (e.g. "recreate reference icon X from a text description") run as part of release qualification, not just unit tests.

---

## 12. Technology Stack

**Decision: start with a Python backend end-to-end** (Gateway, Dispatcher, and the Geometry/Curve/Effects/Boolean/Animation engines all in one Python service for v0), and extract specific hot/numerically-sensitive paths to a compiled language later only if profiling or determinism testing actually demands it. This favors implementation speed for M0–M2 over up-front performance headroom; §12.2 defines the explicit trigger conditions for when to extract something.

### 12.1 v0 Stack (Python-first)

| Layer | Choice | Rationale |
|---|---|---|
| Tool Gateway + Dispatcher | **Python 3.12, FastAPI**, single monolithic service (Gateway and Dispatcher as internal modules, not separate processes, for v0) | Fastest path to a working end-to-end loop; FastAPI gives request/response validation via Pydantic models generated from the same JSON Schemas in the registry, so schema and code don't drift. One process also avoids a network hop between Gateway and Dispatcher until there's a real reason to split them. |
| Schema Registry | JSON Schema (Draft 2020-12) files, versioned in-repo; validated via **Pydantic v2** models (generated or hand-mirrored from the schemas) plus `jsonschema` for the schemas-as-source-of-truth path | Keeps the public contract language-independent even though v0 happens to implement it in Python; if the Gateway is ever rewritten, the schemas don't move. |
| Scene Graph representation | Python dataclasses / Pydantic models mirroring §4.3, immutable-by-convention (return new objects rather than mutate) | Matches the versioning model in §4.6 without needing a compiled language to enforce it — discipline is enforced by code review + property tests (§11.4), not the type system. |
| Curve Engine | Python, using **closed-form math only** (§8.1) — e.g. manual Catmull-Rom → cubic Bézier conversion via `numpy`, or `scipy.interpolate` calls restricted to non-adaptive, fixed-parameter modes | Determinism in §8.1 is about *algorithm choice* (closed-form vs. adaptive-iterative), not language — a closed-form fit is just as bit-reproducible in Python/numpy as in Rust, as long as summation order and precision (float64 throughout) are pinned. |
| Boolean Engine | Python bindings to **GEOS** via `shapely` (`shapely.union`/`.difference`/`.intersection`) | GEOS is a mature, widely-deployed C++ geometry library with stable, well-documented precision-model behavior (fixed precision grid), reachable from Python with no custom binding work — a pragmatic v0 choice versus building/evaluating Rust geometry crates from scratch (§14 open question #2 is deferred, not solved, by this choice). |
| Effects / Style resolution | Python, plain declarative dict/model transforms | No heavy math; language choice is irrelevant here. |
| Animation Engine | Python, keyframe interpolation via straightforward fixed-formula lerp/easing functions (no adaptive solvers) | Same closed-form-only discipline as the Curve Engine keeps this deterministic without needing Rust. |
| Renderer (SVG serializer) | Custom Python SVG serializer writing canonical, fixed-precision, fixed-attribute-order XML directly (not templated strings) | Full control over byte-for-byte output is easier with an explicit serializer than any general-purpose SVG library's defaults. |
| Renderer (rasterization for `render_preview`) | Shell out to **`resvg`** (prebuilt binary/CLI) or use `resvg`'s Python bindings if available, rather than a browser-based renderer | Rasterization is the one place a mature, deterministic native tool is worth depending on even in a Python-first stack — avoids reimplementing an SVG rasterizer and avoids Chromium/WebKit non-determinism. This is a dependency, not a rewrite of engine logic in another language. |
| PDF Export | `cairosvg` or a direct SVG→PDF path via `reportlab`/`svglib`, consuming the same canonical SVG the Renderer produces | Keeps export deterministic by feeding it the already-canonicalized SVG rather than re-deriving geometry. |
| Fonts (Text objects) | Same as v0.2 design: a small embedded, versioned, license-cleared font set (e.g. **Inter** + a monospace family), loaded explicitly by path — no OS font resolution | Language-independent requirement; Python just needs to reference the same embedded font files. |
| Scene Graph Store | Append-only operation log in **PostgreSQL** (via SQLAlchemy or a lightweight query layer) + an in-memory materialized snapshot per active document session (plain Python dict/LRU, or Redis if multi-process) | Same design as v0.2; Postgres client support in Python is mature, no change from the original plan. |
| Asset Storage (images) | S3-compatible object storage (`boto3`), content-addressed keys | Unchanged from v0.2. |
| Tool-call transport | **MCP (Model Context Protocol)**, via the official Python `mcp`/FastMCP SDK, served from the same Gateway process | Matches the PRD's JSON-only requirement directly and is the native way an LLM agent discovers/calls the 21 public tools — no custom protocol needed, and it reuses the same JSON Schemas from the Tool Schema Registry as MCP tool input schemas (single source of truth, no duplicate schema maintenance). A plain HTTP/FastAPI surface is kept underneath for non-MCP clients (debug tooling, direct API access) but is not the primary interface. |
| Concurrency | `asyncio` for I/O-bound Gateway/Store work; CPU-bound geometry ops (esp. `shapely`/GEOS calls) run in a `ProcessPoolExecutor` or worker pool to avoid blocking the event loop on large boolean operations | Python's GIL makes this the standard mitigation for mixing async I/O with CPU-heavy geometry work; also gives a natural boundary for later extraction (§12.2) since the pool interface can point at a different implementation without touching the Gateway. |
| CI / Golden Regression | `pytest` running the golden regression suite (§11.3) on a pinned Python + `numpy`/`shapely`/GEOS version, single controlled build image | Cross-platform float drift risk (§8) means the CI image's library versions are pinned exactly, same discipline as would be needed for a Rust build. |
| Observability | Structured logs + metrics (OpenTelemetry Python SDK) on every tool call | Unchanged from v0.2. |

### 12.2 When to Extract to a Compiled Language

Python is not assumed to be the permanent implementation for every layer — it's the fastest way to reach a working, testable M0–M2. The following are explicit, measurable triggers (not vibes) for extracting a specific engine into Rust (or another compiled language) as a native extension (`pyo3`) or sidecar service, keeping the Python Gateway/Dispatcher unchanged:

| Trigger | Likely candidate to extract |
|---|---|
| §9.1 p95 targets missed by >2x under realistic batch load after query/algorithm optimization is exhausted | Curve Engine or Boolean Engine (whichever profiles hottest) |
| GEOS/`shapely`'s precision-model behavior can't be made to satisfy the §8.2 canonicalization requirements on a specific edge case | Boolean Engine only |
| Sustained multi-tenant load makes the `ProcessPoolExecutor` approach itself the bottleneck (process-spawn/IPC overhead, not the geometry math) | Whole numeric-op pool → sidecar service |

This keeps §8's determinism rules unchanged regardless of implementation language — they were written as algorithm-level constraints (closed-form fitting, fixed tolerances, canonical ordering) specifically so the language choice is decoupled from the determinism guarantee. Rewriting §12.1's Curve/Boolean Engines in Rust later, if triggered, should not change any golden-suite output, since the underlying algorithm and tolerances stay identical — only the runtime changes.

### 12.3 MCP-Specific Design Notes

The engine is exposed as an **MCP server**; the 21 public tools (§5.1) are registered as MCP tools, generated from the same Tool Schema Registry entries used for internal validation. A few protocol-level decisions follow from that:

- **Session ↔ document binding**: `document_id` is passed explicitly as a tool argument on every call rather than assumed from connection state, so the design stays correct even if a single MCP session is later used across multiple documents, or a document is accessed from more than one session (e.g. a resumed conversation).
- **Tools vs. Resources**: the read-only `describe_scene`, `describe_object`, and `render_preview`/`render_objects` calls are strong candidates for exposure as **MCP resources** (addressable, cacheable, cheaper for the LLM to re-reference) in addition to being callable as tools — worth prototyping both and comparing token cost/latency before committing, rather than assuming tools-only is correct by default.
- **Batching stays load-bearing**: MCP's per-call overhead means `batch` (§5.5) isn't just a token-efficiency nicety — it's the main lever keeping multi-object scene construction from turning into dozens of sequential round trips. `atomic: true` batches remain the recommended default for multi-step scene edits.
- **Error surface**: MCP tool call failures should still return the structured `{status: "error", error_code, ...}` shape from §5.2 inside the tool result, not just an MCP-level protocol error — so the LLM gets an actionable, schema-consistent error rather than an opaque transport failure.
- **Versioning**: the MCP server advertises a tool-set version (tied to the Tool Schema Registry version, §5.2) so an LLM client can detect a stale cached tool list after an engine upgrade. *(resolves review round 2, #6)* For a **live session mid-conversation**, the server does not swap a session's effective tool schemas out from under it: a session pins the tool-set version active at its start, and continues being served that version (including old-version engine behavior for determinism per §8.3 rule 5) until the session ends. A new schema version only takes effect for new sessions. This avoids an in-flight LLM conversation suddenly getting a changed tool contract it didn't ask for and can't see coming.

---

## 13. Milestones (proposed)

| Phase | Deliverable |
|---|---|
| **M0a** | **Validation spike (see companion MVP TDD)** — smallest possible slice of the tool set, tested against a real LLM on concrete drawing tasks. **Hard gate**: M1+ does not start until this produces evidence the coarse-outline + constraints approach yields usable results (per the MVP TDD's success criteria). *(resolves review round 2, #5 — this was previously implied, not a real checkpoint)* |
| M0b | Full Python/FastAPI + MCP service skeleton; Scene graph schema + Tool Schema Registry + `create_document`/`create_region`/`describe_scene`/`render_preview` (production version, hardened beyond the spike) via `numpy` curve fitting + `resvg`-shelled rasterization; coordinate system finalized |
| M1 | Full geometry/transform/style tool set + text/image/guide type discriminators + batch + checkpoint/restore + input-size guards; `ProcessPoolExecutor` wired in for geometry ops |
| M2 | Boolean engine (`shapely`/GEOS) + constraints system + style/metadata-conflict resolution |
| M3 | Animation engine (groups, keyframes, export) — puppet-style scope per §10.1 |
| M4 | Determinism hardening (golden suite, semantic-leak lint, fixed-precision serialization, curve/boolean edge-case corpus) — validated against the pinned Python/`numpy`/GEOS versions from §12.1 |
| M5 | Export surface: SVG, PDF, Canvas, animation packages; embedded font set finalized |
| M6 | Performance pass against §9.1 targets; load testing; output-quality benchmark suite (§11.6) wired into release qualification; evaluate §12.2 extraction triggers against real load data |

---

## 14. Remaining Open Questions

1. **Curve-fit quality vs. determinism tradeoff** — fixed-iteration fitting may underperform adaptive solvers on complex outlines; needs empirical tuning of default constants against the outline-fidelity metric (§11.6).
2. **Boolean operation library choice** — needs a concrete evaluation of candidate Rust geometry crates against the determinism requirements in §8.2 before M2.
3. **Preview delivery format** — raster reference vs. richer structured vector description; affects LLM "vision" cost and multimodal dependency; revisit after M0 usage data.
4. **Character animation path** — decide between §10.1's path 1 (puppet-style, no engine change) and path 2 (bone/deformation system, new TDD) before M3 is scheduled on any roadmap that promises true character rigging.
5. **Garbage collection of orphaned undo branches** (§7) — storage growth policy not yet defined; needs a retention/cleanup design before production scale.

---

*End of TDD v0.2.*
