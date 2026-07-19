# AVGE Tool Improvement Backlog

This backlog captures recurring gaps found while recreating dense anime-style environment scenes. These are implementation candidates, separate from the skill-guide usage rules in `docs/environment-guidelines.md`.

## Environment Compound Helpers

### `generate_cloud`

Create a soft, irregular cloud group in one call.

Suggested params:

| Param | Purpose |
|---|---|
| `cx`, `cy` | Cloud center in normalized canvas coordinates. |
| `width`, `height` | Overall cloud bounding size. |
| `puff_count` | Number of overlapping lobes. |
| `puff_variance` | Size and position irregularity. |
| `shade_direction` | Light direction for top/bottom shading. |
| `blur` | Edge softness in pixels. |
| `opacity` | Overall transparency. |

Expected behavior: generate overlapping soft lobes, optionally union them, add a lighter top and subtle underside shade, then blur the silhouette.

### `generate_shape(pattern="cornice")`

Create a thin decorative band along a facade or roof edge.

Suggested params: `region_id`, `edge`, `depth`, `style`, `fill`, `stroke`, `stroke_width`, `z_index`.

### `generate_shape(pattern="awning")`

Create an angled canopy over a door, storefront, or window.

Suggested params: `region_id` or `anchor_point`, `edge`, `width`, `height`, `tilt_angle`, `stripe_count`, `colors`, `z_index`.

### `generate_shape(pattern="rooftop_props")`

Scatter small rooftop silhouettes such as tanks, vents, antennae, and AC units.

Suggested params: `region_id`, `edge`, `count`, `seed`, `prop_types`, `density`, `scale_range`, `z_index`.

## Shading Improvements

### `add_shading(mode="gradient")`

Current `add_shading` works best for hard two-tone accents. Architecture needs continuous per-plane shading.

Suggested behavior:

- `mode="two_tone"`: current behavior.
- `mode="gradient"`: define/apply a 3-5 stop gradient across the region along `light_direction`.
- Optional `strength`, `highlight_color`, `shadow_color`, and `mid_color` controls.

## Scene-Quality Helpers

### Guide-layer export safety

Final export should warn or optionally exclude guide layers/regions.

Suggested behavior:

- `export_svg(exclude_layers=["guides"])`, or
- `critique_preview` finding: `construction_guides_visible`.

### Road-plane stripe helper

Crosswalks, lane dividers, arrows, and floor tiles are common enough to deserve a helper.

Suggested tool: `create_surface_stripes(target_quad, count, orientation, start_v, end_v, stripe_width, spacing_falloff, fill, opacity)`.

Expected behavior: generate evenly spaced `project_quad` stripes in surface coordinates so road/floor markings converge correctly.

### Facade detail pack

`create_facade_grid` handles windows but not secondary architectural clutter.

Suggested tool: `create_facade_details(target_quad, density, include=["cornice", "sills", "mullions", "awnings", "pipes"], seed)`.

Expected behavior: add trim, sills, small ledges, awnings, and pipes behind signage with correct `z_index` defaults.
