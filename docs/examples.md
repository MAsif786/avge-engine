# AVGE Examples

Real illustrations built with AVGE tools. Each is a saved document that can be restored, re-rendered, or edited.

---

## Fridge Night Scene

A detailed kitchen scene with a fridge, countertop, and evening lighting. Demonstrates multi-layered construction with cel-shaded highlights and shadows.

- **124 regions** — fridge body, door, handle, interior shelves, counter, wall tiles, floor
- **Techniques**: `create_region` for boxes, `add_shading` for directional highlights, `restyle` for color tuning
- **Style**: Cel-shaded with warm ambient + cool shadow tones

---

## Kael Storm — Anime Character

Full-body anime character with layered hair, costume details, and cel-shaded lighting.

- **136 regions** — head, hair (3 layers), torso, arms, belt, boots, cape
- **Techniques**: `segmented_chain` for curled hair strands, `armature` for limb posing, `add_shading` for skin/cloth shadows
- **Style**: Anime cel-shade with line-art strokes

---

## Bedroom Scene

A teenager's bedroom with bed, desk, window, posters, and scattered items.

- **190 regions** — the largest example
- **Techniques**: `create_primitive` (rects for furniture), `create_curve` (blanket folds, curtain drapes), `duplicate` (radial for wall clock, grid for tiles)
- **Style**: Flat-color 2D illustration with depth via z-ordering

---

## Hand and Armature Studies

Procedural skeletons and segmented chains exploring limb anatomy.

| Study | Segments | Approach |
|-------|----------|----------|
| Basic hand | 5 fingers | `segmented_chain` with joint radii |
| Armature skeleton | 15+ bones | Node-edge graph with `armature()` |
| Fist pose | 5 curled fingers | Per-finger angle parameters |
| Arm with muscles | 8 segments | Tapered width_start/end for "swollen middle" |

- **Techniques**: `armature` with `junction_separation` + `junction_radius` for clean joint gaps, `segment_chain` with `angle_delta` for curled fingers

---

## UI and App Icons

App icons, logos, and UI mockups built from primitives and boolean operations.

- **Examples**: Code Genesis logo, YouTube thumbnail mockup, Instagram post layout, OpenAI-style avatar
- **Techniques**: Boolean `subtract` for cutouts, `union` for merged shapes, `mirror_region` for symmetry

---

## What These Demonstrate

| Capability | Example |
|---|---|
| **Procedural geometry** | Curled hair via `segmented_chain`, skeletons via `armature` |
| **Boolean operations** | Complex cutouts and merged armor plates |
| **Shading** | Directional highlight/shadow on any region |
| **Primitives** | Furniture, appliances, logos |
| **Curves and lines** | Clothing folds, face outlines, decorative strokes |
| **Duplication patterns** | Radial clock faces, grid tiles, mirror symmetry |
| **Text and images** | Labels, branding elements |
| **Batch operations** | Multi-region color changes in one call |
