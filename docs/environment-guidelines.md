# AVGE Skill: Environment & Architecture Guidelines

_Resource: `avge://skill/environment-guidelines`_
_Sibling to `avge://skill/design-guidelines` (character/object work). This skill governs street scenes, building exteriors, interiors, and any scene where perspective, depth, and repeated architectural elements matter more than a single subject._

_Tool names below are current as of `m0b-v18` (56 tools): `clone_document`, `create_perspective_grid`, `apply_depth_haze`, `create_facade_grid`, `create_surface_stripes`, `create_shadow`, `critique`, `generate_cloud`, `create_line_pattern`, `apply_brush_style`, `set_layer_role`, `apply_texture_effect`, region/primitive/curve `outline_pattern`/`fill_pattern`, `add_shading(mode="gradient")`, and `duplicate`'s `scale_falloff`/`spacing_falloff` params. Existing-region targeting uses the shared selector shape: `ids`, `group_name`, `layer`, `fill`, `tags`, `bounds`, `z_min`, `z_max`, `has_stroke`._

_Implementation backlog for missing helpers: `docs/tool-improvement-backlog.md`._

---

## 1. Construction order — build in this sequence, not detail-first

Environment scenes fail most often when detail is added before structure is locked. Follow this order and don't skip ahead:

1. **Horizon + vanishing points.** Call `create_perspective_grid` first, before any region exists. Pass one entry in `vanishing_points` for a one-point scene, two for two-point (see §2), and set `horizon_y` deliberately before drawing anything. Leave `include_horizon: true` so the horizon line itself is visible as a reference while building.
2. **Ground plane.** Road/floor surface, sized and positioned against the perspective grid's guide lines.
3. **Building massing only.** Block in each building as a plain, single-fill silhouette — a `create_primitive` rect for simple boxes, or a `project_quad` panel (with `target_quad` corners read off the perspective grid) for angled faces. No windows, no signage, no shading yet. Confirm the skyline silhouette reads correctly — proportions, spacing, height variety (§4) — before investing in any single building.
4. **Facade detail pass.** Now run `create_facade_grid` per building face — pass the same `target_quad` used for that building's massing panel, plus `rows`/`columns` and `lit_ratio`. This single call replaces individually placed windows. Add trim/structural lines with `create_curve`/`create_primitive` afterward if needed.
5. **Signage & text.** Add last, with `skew_x`/`skew_y` on `create_text` (or routed through `project_quad`) to match each facade's angle (§5). Signage is the most detail-dense element and the easiest to over-invest in early at the expense of the rest of the scene.
6. **Foreground props.** Streetlights, poles, wires, pedestrian markings — placed last since they sit in front of everything and are the easiest to get right once the rest of the scene's scale is confirmed. Use `duplicate`'s `linear` pattern with `scale_falloff`/`spacing_falloff` for receding rows (see §4 below).
7. **Atmospheric/depth pass.** Run `apply_depth_haze` across all building/prop regions (via `selector`), with `near_y`/`far_y` set to the scene's foreground and horizon bounds. Always last for the first construction pass — it needs final geometry and final base colors to blend toward `haze_color` correctly.
8. **Line hierarchy + QA pass.** `apply_line_hierarchy`, then the QA sequence in §9.
9. **Densify pass.** Treat the completed sequence above as a draft, not the final. Run the second-pass workflow in §8 to add overlapping depth, secondary signage, wires, roof props, awnings, and facade clutter.
10. **Final cleanup/export pass.** Delete or hide all construction guide regions/layers before export. No `create_perspective_grid` guide line, temporary sky patch, snap marker, or proportional guide may remain visible in the final render.

Do not jump to step 4 or 5 for one building while others are still at step 3. Bring the whole scene up one step at a time — this is what prevents one over-detailed building next to flat, undeveloped neighbors. After step 10, the exported image must contain no construction scaffolding; if guides are useful while building, put them on a dedicated `guides` layer and delete that layer before export.

---

## 2. Perspective conventions

- **Two-point perspective** is the default for street-level scenes (this is what most anime/manhwa city backgrounds use — verticals stay parallel, the two horizontal axes converge off-canvas left and right). Call `create_perspective_grid` with two entries in `vanishing_points`. Use **one-point** (a single entry) only for a scene looking straight down a corridor/road with a single vanishing point centered on the horizon.
- **Horizon height:** set `horizon_y` to roughly 0.3–0.4 (30–40% down the canvas) for a street-level, human-eye-line shot — not centered, not near the top. A lower `horizon_y` (closer to 0.6–0.7) reads as looking up at tall buildings; a value near 0.1–0.2 reads as an aerial/bird's-eye view. Pick deliberately based on the intended shot, don't default to center.
- **Vanishing point spread:** place both entries in `vanishing_points` well off-canvas (typically 1.5–3x canvas width away from center, i.e. x-coordinates well outside 0.0–1.0) for a natural, non-fisheye convergence. VPs placed too close together produce an exaggerated wide-angle distortion — only use that deliberately for a stylized/dramatic shot.
- **Shared VPs across the whole scene.** Call `create_perspective_grid` once per document and reuse its `vanishing_points`/`horizon_y` values for every subsequent `project_quad` and `create_facade_grid` call's `target_quad`. A common failure is constructing each building independently and eyeballing convergence — this produces buildings that individually look fine but visibly disagree with each other once the scene is assembled. Always derive `target_quad` corners from the shared grid, never freehand them.
- **Verticals stay vertical.** Only the horizontal receding edges converge to the VPs — building verticals (corners going straight up) stay parallel to each other and to the canvas edges. Don't let verticals lean toward a VP; that's a three-point-perspective effect and will look wrong unless deliberately intended. Use `create_perspective_grid`'s `verticals` count to add reference verticals without them converging.
- **Road markings are surface panels.** Crosswalks, arrows, lane stripes, floor tiles, and plaza seams must be generated with `create_surface_stripes` on a shared road/floor quad, or as explicit `project_quad` panels. Do not place independent parallelograms by eye. A correct zebra crossing has even spacing in road-plane coordinates and foreshortens toward the horizon.

---

## 3. Palette discipline

- Establish the scene's palette **before** building massing (step 3), via `generate_palette`, not per-building as you go. Reusing one generated harmony across every building keeps the scene cohesive.
- Target a restrained core: roughly 4–6 base hues for building fills (varied by material/shade, not by inventing new hues), plus 1–2 accent hues reserved for signage/highlights. A scene that uses a new arbitrary hex per building reads as disorganized no matter how correct the perspective is.
- Cool, slightly desaturated hues (blues, teals, muted violets) read well for building faces in shadow or ambient light; reserve fully saturated warm colors (reds, oranges, yellows) for signage, lit windows, and small accent elements — that contrast is what makes signage pop against the architecture rather than everything competing for attention.
- Sky-to-building color relationship matters: buildings farther back should trend toward the sky's hue as distance increases (this is what §6's atmospheric pass automates — but the base palette should already be compatible with that shift, not fighting it with a totally unrelated sky color).
- Reuse existing hex values already in the scene (check `describe_scene`) for minor elements — trim, frames, small props — rather than introducing new arbitrary colors, same convention as the character/object design guidelines.

---

## 4. Density & silhouette variety

Real streets read as real because nothing is perfectly uniform. When using `duplicate` or repeated `generate_shape` calls for buildings, windows, or props, deliberately vary:

- **Building height and width** — ±20–40% variation between adjacent buildings, even when they're otherwise similar in style. A row of identical-height buildings reads as an obvious repeated asset.
- **Facade rhythm** — not every building needs the same `create_facade_grid` `rows`/`columns` density. Mix taller/denser buildings (more rows) next to shorter/simpler ones.
- **Window lit/dark ratio** — vary `create_facade_grid`'s `lit_ratio` building-to-building (one building mostly lit, its neighbor mostly dark) rather than applying the same ratio everywhere. Give each building its own `seed` so window layouts don't visibly repeat, and use `variation` for subtle per-window inset differences so the grid doesn't read as mechanically uniform.
- **Signage size and placement** — avoid uniform sign sizes stacked at identical heights across every building front; stagger them the way real storefront signage is staggered.
- **Receding props** — for streetlights/poles down a street, use `duplicate`'s `linear` pattern with `scale_falloff` and `spacing_falloff` set so copies shrink and draw closer together with distance, rather than flat uniform `dx`/`dy` spacing (which looks wrong for anything receding into depth).
- Use `duplicate`'s `variations`/`jitter` params wherever repeating an element (poles, railings, non-facade details) to introduce small natural irregularity instead of mechanically perfect repetition — a mechanically perfect grid is one of the fastest tells of unrefined vector art.
- **Facade details are not optional after massing.** Every visible building face that is large enough to read as a building should receive at least one facade-detail pass: `create_facade_grid` for windows, plus secondary structural marks such as floor lines, mullions, cornices, awnings, trims, or rooftop silhouettes. A sign on a flat block is not facade detail; it is a board pasted on a massing shape.
- **Layer facade detail under surface-mounted boards.** Window grids, floor lines, and mullions belong behind signs and awnings mounted on the same facade. The correct stack is: base building face, facade grid/trim, shadows/glass highlights, sign panel, sign text/graphics, foreground props. If windows draw across a board, lower their `z_index` or move the board/text higher.

---

## 5. Signage & surface-mounted detail

- Any text or image sitting on an angled building face must be skewed/warped to match that face's angle — use `create_text`'s `skew_x`/`skew_y` params, or route the whole sign through `project_quad` (create the panel warped to the same `target_quad` as the facade beneath it, then treat text placement relative to that panel). Flat, axis-aligned text on a receding facade is an immediate tell that breaks the perspective illusion, regardless of how correct the building geometry underneath is.
- Match the perspective convention already established for that facade — reuse the same `target_quad` (or the `perspective`/`skew_x` value if the surface came from `create_ellipse_band`) that built the facade panel and its `create_facade_grid` call, don't independently guess the angle for the sign.
- Keep sign color within the accent-hue budget from §3 rather than introducing new saturated colors per sign.
- Sign panels should occlude windows and trim beneath them. After adding signs, inspect a crop: no window rectangle, facade floor line, or grid stroke should cross through the sign board or text unless it is deliberately a transparent glass sign.
- Use more than one signage layer on dense commercial streets: large building-mounted ads, smaller storefront boards, vertical blade signs, and shallow hanging panels. Put these at different `z_index` depths and sizes; one sign per building reads sparse and game-like.

---

## 6. Atmospheric depth pass

- Run `apply_depth_haze` across all building/prop regions (via `selector`) once geometry and base colors are final — never before, since it needs real final colors to blend from.
- Set `near_y` to the scene's foreground edge and `far_y` to the horizon line (matching `create_perspective_grid`'s `horizon_y`) so the haze falloff tracks actual depth in the shot — for a street scene, distance correlates with vertical position between the horizon and the foreground.
- Set `haze_color` to (or near) the sky's base color so distant buildings visually blend toward the sky rather than toward an unrelated gray — this is what sells the "melting into the horizon" look.
- Keep `max_strength` moderate for near/mid-ground and let the `near_y`/`far_y` falloff do the work of making it more pronounced near the horizon — a `max_strength` that's too high will wash out too much of the scene's palette work from §3; too low is the more common failure and the one most responsible for flat-looking results.
- Consider running `affect_stroke: true` alongside `affect_fill` so distant buildings lose contrast in their outlines too, not just their fills — pair this pass with `apply_line_hierarchy` (thinner strokes further back) rather than treating them as unrelated passes.
- Re-run `apply_depth_haze` after the densify pass if new overlay regions were added on top of previously hazed buildings. A common failure is hazing the original `architecture` layer, then adding later correction panels/sign-adjacent facade details on another layer that bypasses the haze and restores flat saturation.
- If far/center buildings still read equally saturated as foreground buildings, increase `max_strength` or target far-region IDs explicitly with `selector={"ids":[...]}`. Underdoing haze on the farthest buildings is more common than overdoing it.

---

## 7. Per-Surface Shading And Sky Detail

Architecture usually needs continuous plane shading, not only flat fills or hard two-tone offsets.

- For building faces, prefer `add_shading(mode="gradient")` or `define_gradient` + `restyle(fill_gradient=...)` for broad light-to-shadow transitions across the facade. Use the default two-tone `add_shading` for small props or hard cel-shaded accents; flat single-fill building faces should be treated as unfinished unless the style is deliberately icon-flat.
- Each major facade should have a light-side and shadow-side read. A simple approach is one base `project_quad`, one low-opacity shadow strip along the receding edge, and one thin highlight line along the sun-facing edge.
- Skies need designed cloud groups, not single ellipses. Use `generate_cloud(cx, cy, width, height, puff_count, puff_variance, shade_direction, blur, opacity)` for overlapping soft puffs with a lighter top lobe, darker underside, low opacity, and blur. Avoid hard, perfectly symmetric white ovals.

---

## 8. Densify Pass — first construction pass is only a draft

The construction order in §1 creates a correct scene, but correctness is not enough for a rich anime background. After completing the first pass, run a deliberate densify pass:

1. **Run `critique(mode="visual")`.** Treat `too_flat`, weak depth, low-density, missing shadow, or bad-perspective findings as instructions to continue, not as optional polish.
2. **Stagger buildings in depth.** Re-examine the massing layer and add at least a few overlapping silhouettes: a shorter foreground building crossing in front of a taller rear building, a side wall partly hidden by a sign, a roofline cutting across a neighbor, or a storefront band in front of a tower base.
3. **Add secondary architectural clutter.** Add cornices, awnings, roof-edge rails, rooftop boxes/tanks/vents, antennae, vertical pipes, small AC units, window sills, and trim. Use `project_quad`/`create_curve`/`duplicate` against existing facade edges instead of freehand placement.
4. **Add second-layer signage.** Add smaller signs at different depths and scales after the primary signs are placed. Dense commercial streets need overlapping boards and blade signs, not one clean panel per building.
5. **Add connective props.** Add wires/cables, poles, lamp arms, railings, bollards, and curb details after the building/sign composition exists. Use `duplicate(pattern="linear", spacing_falloff=..., scale_falloff=...)` for receding repeated props.
6. **Add controlled linework texture.** Use `create_line_pattern(pattern="hatch"|"cross_hatch"|"contour_hatch")` for free shading fields. When the texture belongs to a created object, use `fill_pattern="hatch"|"cross_hatch"|"scribble"|"stipple"`; when the border/curve itself should be stylized, use `outline_pattern="dashed"|"dotted"|"wavy"|"zigzag"|"rough"|"sketch"|"tapered"|"pressure"`. Use `role="construction"` only on guide layers and exclude those layers from final export.
7. **Re-run haze and line hierarchy.** Any densify pass that adds visible building panels or far props must be followed by another `apply_depth_haze` and stroke hierarchy pass, otherwise new overlays pop forward.
8. **Crop-inspect dense areas.** Use `render_preview` crops around the busiest signs/facades to catch bad layering, unwarped labels, window grids drawn over boards, or free-floating props.

Proposed tool improvements for this pass:

- Use `generate_shape(pattern="cornice")` to create a thin decorative band along a region's top edge, with `depth` and `style` (`flat`, `stepped`, `molded`).
- Use `generate_shape(pattern="awning")` to create an angled canopy over a door/window or facade edge, with `width`, `tilt_angle`, `stripe_count`, and stripe colors.
- Use `generate_shape(pattern="rooftop_props")` to scatter rooftop silhouettes such as tanks, vents, antennae, and AC units along a roof edge with `count`, `seed`, `prop_types`, and `density`.

Do not skip this pass because the first checklist technically completed. "Sparse but valid" is still a failed environment background when the reference is a dense commercial street.

---

## 9. QA checklist — when to call what

Run this sequence, not just a single check at the end:

1. **After massing (step 3):** `critique(mode="rules")` — catches off-canvas objects, gross proportion problems, and stroke-uniformity issues while they're still cheap to fix, before any facade detail is invested.
2. **After each building's facade pass (step 4), before moving to the next building:** `render_preview` with `region_id` cropped to that building, to inspect window density/alignment up close — small facade errors are easy to miss in a full-canvas view.
3. **After signage (step 5):** re-check that skew/perspective on text matches its facade — a quick `render_preview` crop on any building with signage.
4. **After the atmospheric pass (step 7):** `critique(mode="visual")` — this is the tool that flags `too_flat`, `bad_perspective`, and similar visual-read issues, and it's most meaningful once color/depth work is actually complete.
5. **After the densify pass (§8):** run `render_preview` crops around overlapping signs, facade grids, and road markings. Check that all new elements still obey perspective and layering.
6. **Before final export:** confirm no region on `guides` layer or named like `guide_*` remains visible; then use `compare_style_consistency` if this is one scene among a multi-panel/sequential set.

Don't defer all QA to the end — per `critique(mode="rules")` guidance, catching a perspective or grounding mismatch after one building is far cheaper than discovering it once ten buildings share the same mistake.

---

## 10. Common failure patterns to specifically avoid

- Construction guide lines visible in final render.
- Flat, full-saturation distant buildings with no haze — the single most common flatness tell.
- Adjacent buildings whose receding edges visibly disagree — each was likely constructed against its own guessed angle instead of a shared `create_perspective_grid`.
- Road markings placed as loose parallelograms instead of road-plane `project_quad` panels with coherent spacing.
- Windows/floor lines drawn over signage boards because facade detail has a higher `z_index` than the sign.
- Large building faces with only a flat fill and one sign, skipping `create_facade_grid` and secondary trim.
- Perfectly uniform window grids with no lit/dark variation and no size jitter.
- Axis-aligned (unskewed) text/signage sitting on a clearly angled facade.
- Streetlights/poles repeated at uniform size/spacing instead of using `duplicate` with `scale_falloff` and `spacing_falloff`.
- Every building at identical height and width, revealing an obviously duplicated asset.
- Horizon line placed without a deliberate reason (accidentally centered, or mismatched with the intended eye-level of the shot).
- Uniform stroke weight across foreground and background elements — nothing differentiates near from far except color.
