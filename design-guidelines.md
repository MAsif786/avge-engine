# AVGE Design Skill
### Aesthetic conventions for the AVGE tool-calling agent

**Purpose:** the AVGE engine gives you geometric and stylistic capability (fills, strokes, gradients, opacity, layering, effects) — this skill tells you *when and how* to reach for that capability so results look intentional rather than like a generic clip-art placeholder. Geometry correctness (proportion, symmetry, recognizability) is necessary but not sufficient — this skill is about the remaining 30% that separates "technically a coffee cup" from "a coffee cup someone designed."

Apply this skill on every `create_region`/`style_objects` call, not as a final pass — retrofitting flat shapes with depth after the fact costs more tool calls than building it in from the start.

---

## 1. Every filled region gets depth, not a flat fill

A single flat `fill` color reads as a placeholder. Before finalizing a region's style, choose one:

- **Two-tone shading**: split a curved/rounded surface into a "lit" region and a "shadow" region using two adjacent Regions of the same hue family (e.g. base `#E8D4B0` + a darker `#C9AD82` sliver along one edge to imply where light doesn't reach). This is what worked well in the coffee cup's liquid surface (two nested browns) — extend that same trick to every major surface, not just the ones that happened to need it structurally.
- **Gradient fill** where the tool supports it: light-to-dark along the axis facing away from an assumed light source (default: upper-left).
- **A thin highlight stroke or region** (very light tone, low opacity, positioned along one edge) reads as reflected light and is cheap — 1 extra region, disproportionate visual payoff.

Reserve pure flat fill for genuinely flat-by-design objects (icon-style silhouettes, background shapes) — make that a deliberate choice, not the default.

## 2. Line weight is a hierarchy, not a constant

Don't give every stroke the same width. Establish 2–3 tiers per composition:
- **Outer/primary silhouette**: heaviest stroke (defines the object against the background).
- **Internal structural lines** (e.g. cup rim, window panes): medium.
- **Fine detail** (highlights, texture lines): thinnest, or no stroke at all (fill-only).
Uniform stroke width everywhere (as seen in the MVP results so far — most objects used `width=0.005` across nearly every region) is the single fastest visual tell of an unstyled result. Vary it deliberately.

## 3. Palette: pick 3–5 colors with a relationship, not independent choices per region

Before creating any region, decide the palette as a set, not one color at a time:
- **Analogous** (adjacent hues — warm browns/tans for the cup, greens for a tree) for a calm, cohesive object.
- **Complementary accent**: one small element in a contrasting hue draws the eye (e.g. a warm cup with a single cool-toned accent).
- Avoid pure saturated primaries (`#FF0000`, `#00FF00`, `#FFFF00`-family flat colors) unless the brief calls for a literal flat/icon style — they read as unconsidered defaults. Slightly desaturated, warmed, or cooled variants read as chosen.
- Reuse the same 3–5 hex values across all regions in a scene rather than picking a new arbitrary color per region — visual coherence comes from a shared, small palette, not variety.

## 4. Ground objects with shadow or context, don't float them

A subject centered on pure white with no grounding cue reads as a sticker, not a scene. Cheap, high-payoff additions:
- A soft ground shadow region (low-opacity dark ellipse/shape beneath the subject) — as the coffee cup benchmark already did with its saucer, extend the same instinct even when the prompt doesn't explicitly ask for a supporting surface (e.g. a subtle shadow under a smiley face's chin, a ground-line under a star if it's meant to sit in a scene rather than float as a pure icon).
- Whether to ground an object is itself a style decision — flat icon-style compositions (app icons, logos) *should* float; representational/scene-style compositions should not. Decide which register the prompt calls for before defaulting to either.

## 5. Composition: use the canvas deliberately

- Default centering (bounding box centered in the 0–1 canvas) is a safe fallback, not a design choice — deliberately shift the subject off-center (e.g. lower-third, or offset toward negative space) when the composition benefits, especially for scene-style (not icon-style) prompts.
- Leave breathing room: a subject that fills 90%+ of the canvas edge-to-edge reads as cramped. 70–80% of the canvas's shorter dimension is a reasonable default fill ratio for a single-subject composition.
- For multi-element scenes (house, tree), vary element scale intentionally rather than making every sub-part roughly equal size — visual hierarchy needs one dominant element and supporting smaller ones.
- **Proportion relative to scene context**: an object's canvas footprint must match how it fits in a real scene. A desk is ~90–100% of the canvas width; headphones resting on it are ~15–25%; a water bottle is ~6–8%. Before creating any region, estimate what fraction of the canvas it should occupy by comparing it to the real-world object it represents alongside the other objects in the scene. The most common proportion mistake is making standalone objects too large (filling 40–50%+ of canvas width when they should be 15–25%). A good heuristic: if the item sits on a surface, its width should be ≤¼ of the surface's width unless it's the sole subject.

## 6. Match the style register to the prompt, and hold it consistently

Before the first `create_region` call, decide (even implicitly) which register this composition is in, and keep every subsequent choice consistent with it:
- **Flat/icon style**: bold flat fills, minimal-to-no shading, thick uniform-ish outlines, geometric simplicity. (Rules 1–2 relax here — flat fill is *correct* for this register.)
- **Soft/organic style**: gradients or two-tone shading throughout, rounded corners (`smoothness` biased high), softer/muted palette.
- **Line-art style**: little to no fill, all definition carried by stroke weight hierarchy (Rule 2 becomes the primary tool).
Mixing registers within one composition (e.g. one region flat-shaded, the next gradient-shaded, for no compositional reason) is what makes a result look inconsistent even when each individual region is fine in isolation.

## 7. Self-check before finishing (use `render_preview`, not just `describe_scene`)

Structural correctness doesn't surface aesthetic problems — visual review does. Before returning a final result, look at the preview and ask:
- Does anything look flat/pasted-on rather than dimensional? → apply Rule 1.
- Is every stroke the same weight? → apply Rule 2.
- Are the colors an arbitrary grab-bag, or a considered set? → apply Rule 3.
- Does the subject look grounded or like a floating sticker — and is that the right choice for this prompt's register? → apply Rule 4.
- Is the composition centered-by-default, or centered-on-purpose? → apply Rule 5.
- Do the objects obey real-world proportions — is each the right size relative to its container/surface? → see proportion guidance in Rule 5.
- Did you edit the existing document incrementally rather than rebuilding from scratch? → use \ to recolor, \ to remove, \/\ for undo.

This maps directly onto why visual feedback outperformed text-only in the MVP comparison (§4 of the MVP TDD) — \ cannot catch any of the above, since none of it is expressible as bounds/tags. This is a second, independent reason \ earns its cost, beyond the completeness finding already documented.

---

## 8. Character design: ask first, plan the register, build layer by layer

Before creating any region of a human/character, establish the following — either from the prompt's explicit description or by asking clarifying questions first:

### 8a. Decide the style register before anything else

The same character drawn in different registers uses *different proportions, different features, and different construction rules*. Decide upfront, then stay consistent:

| Register | Head-to-body ratio | Eyes | Nose | Mouth | Skin/shading |
|---|---|---|---|---|---|
| **Anime / manga** | 1:4–1:6 (large head) | Large, detailed iris + shine, often simplified lids | Small or omitted (just a shadow line) | Small curved line or simple shape | Flat cel-shading, minimal shadows |
| **Realistic** | 1:7–1:8 | Anatomical: whites + colored iris + round pupil + upper/lower lids + brows | Bridge + tip + nostrils clearly defined | Upper lip + lower lip + philtrum | Layered shading (two-tone per Rule 1), skin hue variation |
| **Cartoon / stylized** | 1:3–1:5 (head can be very large) | Simple circles or ovals, minimal detail, big pupils | Cute button or triangle, or omitted | Wide expressive shape | Flat fills, bold outlines, limited palette |
| **Chibi / super-deformed** | 1:2–1:3 (head is ~half the body) | Huge eyes, very large iris, big shines | Tiny dot or omitted | Small dot or curve | Flat fills, simple |

Asking the user "What style? Anime, realistic, cartoon, or chibi?" before starting saves time and avoids rebuilding.

### 8b. Establish character specs before drawing

Ask or determine:
- **Age range** (child, teen, young adult, adult) — affects face proportions (eyes lower on face for younger, higher for older) and body height
- **Gender** — affects jaw shape (softer/rounder vs sharper/angular), shoulder width, hip width
- **Clothing / outfit** — school uniform, casual, formal — determines what parts of the body are visible
- **Pose** — standing, sitting, with props — affects limb placement from the start
- **Viewing angle** — front, 3/4, profile — determines symmetry and visible features

### 8c. Human face proportions (realistic register)

- **Eyes**: positioned at the **vertical center** of the head (not the upper half). Distance between eyes = width of one eye.
- **Nose bottom**: halfway between eyes and chin bottom.
- **Mouth**: halfway between nose bottom and chin bottom.
- **Ears**: top aligns with eyebrows, bottom aligns with nose bottom.
- **Hairline**: roughly ⅓ of the way from crown to eyebrows.
- **Face width**: about ⅔ of head height.

For **anime**: eyes are lower on the face (below center), larger, and the nose is minimal. For **chibi**: the face is mostly eyes and forehead.

### 8d. Human body proportions

| Body part | Realistic (adult) | Anime | Cartoon | Chibi |
|---|---|---|---|---|
| **Head** | 1 unit | 1 unit | 1 unit | 1 unit |
| **Torso + neck** | ~2.5 units | ~2 units | ~2 units | ~1 unit |
| **Legs** | ~4 units (half the height) | ~3-3.5 units | ~2.5 units | ~1-1.5 units |
| **Arms** | reach mid-thigh | reach below hip | reach hip | reach waist |
| **Shoulder width** | ~2 head widths | ~1.5-1.8 head widths | ~1.5 head widths | ~1.2 head widths |

### 8e. Build order (smart layering)

Build the character in this order so each layer guides the next:

1. **Face shape** (oval/round) — establishes position and scale.
2. **Hair base** — covers the top of the face, defines silhouette.
3. **Eyes** — most expressive feature; position determines the rest of the face layout.
4. **Eyebrows** — just above eyes; set expression.
5. **Nose** — subtle; placed by the halfway rule.
6. **Mouth** — below nose; small changes here change expression dramatically.
7. **Ears** — align with eyes/nose.
8. **Neck + torso** — connects head to body; width relative to head.
9. **Arms + hands** — extend from shoulders; hands are ~face-sized.
10. **Legs + feet** — longer than expected (half the total height in realistic).

### 8f. Smart iteration workflow

- Start with a **checkpoint** before adding the face features so you can restore if the proportions are off.
- Use **describe_scene to verify positions** — check that eye y-coordinates match (both eyes at same height), that the nose is centered (x=0.5 for frontal view).
- **Render_preview frequently** — human faces are the most perceptually sensitive subject; bounding-box text feedback is not enough to judge if a face looks right.
- Fix asymmetry with  or  + recreate — never rebuild the full document.
- For complex characters, build the **face and body in separate checkpoint layers**: checkpoint("face_done") before adding the body, so you can adjust body proportions without losing face work.
 (§4 of the MVP TDD) — `describe_scene` cannot catch any of the above, since none of it is expressible as bounds/tags. This is a second, independent reason `render_preview` earns its cost, beyond the completeness finding already documented.
