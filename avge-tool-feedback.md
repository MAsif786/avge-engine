# AVGE Tool Feedback: Hand & Skeleton Generation

## Tool: `armature` — Node-based tapered skeleton generator

### Problem 1: Segment caps extrude to viewport edges

```
input:  wrist(y=0.82, r=0.055), palm(y=0.6, r=0.085)
expect: segment ends at y≈0.875
actual: path hits y=1.0 (viewport edge)
```

The radius at each node causes the tapered segment to extend all the way to the canvas boundary instead of creating a clean perpendicular cap at the node's position.

**Fix:** Cap each segment at the perpendicular bisector of the node position, not at the viewport edge. The segment between node A and node B should be a tapered quadrilateral clipped to the line orthogonal to AB at A and at B.

---

### Problem 2: Zero-height degenerate segments

```
arm_0: bounds h=0.0000  → flat line, not a 2D shape
arm_1: bounds h=0.0000
...
```

Multiple segments shared between nodes produce zero-area shapes, often at branch points.

**Fix:** Add a minimum-bounding check before emitting a segment. If all four control points are collinear (within epsilon), skip the segment or fall back to a circle at the midpoint with the average radius.

---

### Problem 3: Joints don't overlap → union fails

```
palm→index and palm→middle share node "palm"
but segments don't overlap at palm → MultiPolygon → union error
```

When two edges diverge from the same node, the generated segments should overlap at that node so boolean union can merge them.

**Fix:** Extend each segment past its shared node by `max(radius_a, radius_b) * 0.3` so adjacent segments at a branch point overlap. This ensures shapely union produces a single Polygon, not a MultiPolygon.

---

### Problem 4: No style inheritance in generated segments

```
arm_0: fill=#CCCCCC, stroke-width=5
arm_1: fill=#CCCCCC, stroke-width=5
```

Every call to `armature` returns grey segments that need post-hoc restyling.

**Fix:** Accept optional `fill`, `stroke`, `stroke_width`, `opacity` in the armature params dict. Apply them to every generated segment so the output is ready-to-use.

---

### Problem 5: No built-in merge mode

Currently you must:
1. Generate armature segments
2. Call `boolean_operation(union)` separately
3. Handle union errors
4. Restyle

**Fix:** Add `output: "union"` param that merges all segments internally within the armature function and returns a single clean region. The engine already has union — just expose it as an option.

---

## Tool: `segmented_chain` — Chain of segments from an anchor edge

### Problem 6: Uniform segment params for all chains

```
segmented_chain(count=5, segments=[...]) 
→ all 5 fingers get identical segment lengths
→ no middle > ring > index > pinky variation
```

**Fix:** Allow `segments` to be a 2D array — one entry per chain instead of one entry for all chains:

```json
"segments": [
  [{"length":0.13,"width":0.03}, {"length":0.09,"width":0.02}],  // index
  [{"length":0.15,"width":0.032},{"length":0.10,"width":0.022}], // middle
  [{"length":0.14,"width":0.03}, {"length":0.09,"width":0.02}],  // ring
  [{"length":0.09,"width":0.025},{"length":0.06,"width":0.018}], // pinky
  [{"length":0.07,"width":0.035},{"length":0.04,"width":0.025}]  // thumb
]
```

Or simpler: per-chain overrides with `length_scale`:

```json
{"count":5, "length_scales": [0.9, 1.0, 0.95, 0.7, 0.5], ...}
```

---

## Tool: `boolean_operation` — Shape merging

### Problem 7: Union produces excessive boundary points

```
11-segment armature union → 739 points → 34KB SVG
16-segment armature union → 805 points → 37KB SVG
segmented_chain union     → 2505 points → 123KB SVG
```

Every intersection vertex from overlapping segment boundaries is preserved. Output is 10× larger than hand-drawn equivalents.

**Fix:** Add `simplify_tolerance` parameter (Ramer-Douglas-Peucker):

```json
{"operation":"union", "simplify_tolerance": 0.003, ...}
```

This would post-process the union boundary, removing colinear vertices while preserving shape within tolerance. A 2505-point hand would drop to ~200 points.

---

## Tool: `batch` — Multi-operation batch

### Problem 8: Batch is powerful but error messages lose context

When one op in a batch fails, the error doesn't say which one.

**Fix:** Include the `tool` and an index in error messages:
```
Error at op[3] (create_region: "pinky"): Coordinate out of range
```
