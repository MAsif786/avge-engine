# TDD — AVGE Validation Spike (MVP)

**Version:** 0.1
**Status:** Design
**Companion to:** AVGE Technical Design Document v0.4 (production design), AVGE PRD v0.1
**Owner:** Engine Team

---

## 1. Purpose

This is **not** a scaled-down version of the production TDD. It is a separate, deliberately narrow experiment with one job: **find out whether an LLM can produce visually usable vector art through a coarse-outline + JSON-tool-call interface at all**, before investing in the full system described in the production TDD.

Everything here is designed to be thrown away or rewritten once the question is answered. Where the production TDD optimizes for correctness, determinism, and scale, this document optimizes for **speed to a real answer** and **honest measurement**.

**This document does not repeat design already settled in the production TDD** (data model, determinism rules, etc.) except where the MVP deliberately diverges from it. Divergences are called out explicitly in §3.

---

## 2. The Question Being Tested

> Given only a coarse point outline + geometric constraints (smoothness, closed/open, corner style) and a describe/preview feedback loop, can an LLM (no special vector-graphics fine-tuning, general-purpose model) construct a recognizable, reasonably clean depiction of simple named objects — without ever touching SVG or Bézier math directly?

This is the load-bearing assumption of the entire PRD. Nothing else in the production TDD matters if this is false.

**Explicitly not being tested here:** performance at scale, determinism robustness, multi-tenant concerns, animation, export formats, boolean operation correctness at scale, MCP session semantics. Those are real, but they're irrelevant if the core premise fails.

---

## 3. Scope

### 3.1 Tools included (5, not 21)

| Tool | Why included |
|---|---|
| `create_document` | Needed to establish a canvas. |
| `create_region` | The core primitive under test — this is the whole bet. |
| `style_objects` | Fill/stroke are needed for a result to be visually legible at all. |
| `describe_scene` | The LLM's only non-visual feedback — needed to test whether the inspect-and-revise loop works. |
| `render_preview` | The LLM's visual feedback (if the harness is multimodal) — needed to test whether visual review improves results. |

**Deliberately excluded for the spike:** `edit_region`, `delete_region`, `duplicate_region`, `group_regions`, `transform_objects`, `boolean_operation`, all Animation tools, `batch`, `checkpoint`/`restore`, `find_objects`, `render_objects`, `export`. If the core 5 don't produce usable results, none of the excluded tools would have saved the approach — they add capability, not spatial reasoning ability.

### 3.2 Divergences from the production TDD (intentional, temporary)

| Production TDD | MVP divergence | Why |
|---|---|---|
| MCP server, full Tool Schema Registry (§12, §12.3) | Direct Python function calls wrapped as a **single MCP server with only the 5 tools above**, using inline Pydantic schemas (no separate registry files) | Full registry infrastructure is process overhead the spike doesn't need to validate the core question; still uses real MCP so the harness matches the eventual interface, not a fake stand-in. |
| Postgres-backed operation log + checkpoint/restore (§4.6, §7) | **In-memory scene graph only, single process, no persistence.** Document is lost when the process restarts. | Persistence has nothing to do with whether the LLM can draw; building it now is pure waste if the spike fails. |
| Text/Image/Guide type discriminators (§4.5, §4.5b) | **Regions only** — no text, image, or guide objects. | Not needed to test coarse-outline drawing ability. |
| Boolean Engine (`shapely`/GEOS, §6.4) | **Omitted entirely.** | Compound shapes via boolean ops are a capability question, not the core spatial-reasoning question. |
| Input-size/abuse guards (§9.4) | Minimal (outline point cap only, generous — 200 points) | No external/multi-user exposure at spike stage; abuse isn't a real risk yet. |
| §11.2–11.5 (semantic-leak lint, golden regression, fuzz/property tests, load tests) | **Skipped.** Manual code review only. | These protect a production system's long-term integrity; irrelevant to a throwaway spike measured in days. |
| §8 full determinism apparatus (fixed-iteration curve fitting, canonicalized boolean clipping, golden suite) | **Curve fitting still uses closed-form math (Catmull-Rom → Bézier via `numpy`)** — kept, because it's not extra work and keeps results comparable run-to-run — but no golden-suite enforcement or CI gate around it. | Determinism is nearly free to keep here and makes comparing "same prompt, different constraint values" trials meaningful; the *enforcement infrastructure* around it is what's skipped. |
| Auth / multi-tenancy | None — single hardcoded local session | Not a production system yet. |

Stack otherwise matches production TDD §12.1 where used: Python 3.12, FastAPI/MCP SDK, `numpy` for curve fitting, `resvg` (shelled out) for `render_preview` rasterization.

---

## 4. Evaluation Harness

### 4.1 Test Prompts

A fixed, small benchmark set — deliberately simple to start, since if simple objects fail, complex ones certainly will:

1. "Draw a coffee cup" (simple, single closed shape + handle)
2. "Draw a house icon" (compound of simple shapes — tests whether multi-region composition alone, without boolean ops, is enough)
3. "Draw a smiley face" (tests proportion/placement of sub-elements relative to each other)
4. "Draw a simple tree" (tests organic/non-geometric outline quality)
5. "Draw a five-pointed star" (tests precision on a shape with a known, checkable correct answer — symmetry, point count)

5 prompts is intentionally small — this is a qualitative spike, not a statistically powered benchmark. Expand only if results are promising enough to justify a larger evaluation.

### 4.2 Procedure

For each prompt:
1. Give the LLM the prompt + the 5 MVP tools (via MCP) + a short instruction that it may call `describe_scene`/`render_preview` as many times as it wants before finishing.
2. Record: number of tool calls used, final `render_preview` output, full transcript of outline/constraint values chosen.
3. Run each prompt **twice**: once with `render_preview` available (visual feedback loop), once without (text-only `describe_scene` feedback) — this directly tests whether visual feedback is necessary or whether structural description alone is enough, which matters a lot for cost/latency in the production design.

### 4.3 Success Criteria (decide *before* running, not after seeing results)

| Result | Verdict | Action |
|---|---|---|
| Recognizable, reasonably clean shapes across most (4-5/5) prompts, with visual feedback improving results over text-only | **Core premise validated** | Proceed to production TDD M0b+, prioritize keeping `render_preview` cheap (§9.1) since it's earned its cost |
| Recognizable shapes but only with heavy iteration (10+ tool calls per prompt) or only on the simplest prompts (1, 5) | **Partially validated — scope risk** | Proceed cautiously; revisit §4.5c outline-size guidance and constraint defaults in the production TDD before committing to the full build; consider whether the tool set needs richer primitives (e.g. shape templates) rather than pure freeform outlines |
| Consistently blobby, spatially wrong, or unrecognizable output regardless of iteration or feedback mode | **Core premise not validated** | Do not proceed to production TDD build-out; treat this as a genuine negative finding and revisit the fundamental interaction model (e.g. hybrid approach where the LLM selects/parameterizes template primitives instead of raw freeform outlines) before any further engineering investment |

### 4.4 What Gets Reported Back

A short findings memo (not another TDD): the 10 render outputs (5 prompts × 2 feedback modes) side by side, tool-call counts, and a plain verdict against §4.3 — not a redesign. Design changes, if warranted, happen after the finding is in hand, in the production TDD.

---

## 5. Estimated Effort

Roughly 2-4 days for someone familiar with the stack: MCP server + 5 tools + in-memory scene graph + curve fitting + `resvg` preview wiring is a small fraction of the production TDD's surface area. This is the entire point — it should be cheap enough that running it is obviously worth it before committing to the full build.

---

## 6. Explicit Non-Goals

- This is not a design for anything that will run in production.
- No code or schema from this spike is assumed to carry forward as-is — the production TDD's §4/§5 designs remain the target even if the spike succeeds; this just validates the *premise* behind them.
- No performance, security, or scale claims are being tested or should be inferred from spike results.

---

*End of MVP TDD v0.1.*