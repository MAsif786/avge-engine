"""Build a kid's room design using AVGE engine."""
import httpx, json, base64, sys

BASE = "http://localhost:8000"
c = httpx.Client(base_url=BASE)

def r(rid, outline, smooth, closed, fill, stroke=None, sw=0, z=0, op=1.0):
    return c.post("/tools/create_region", json={
        "outline": outline, "region_id": rid, "closed": closed,
        "smoothness": smooth, "fill": fill, "stroke": stroke,
        "stroke_width": sw, "z_index": z, "opacity": op,
        "document_id": DOC,
    })

def batch(ops):
    return c.post("/tools/batch", json={"document_id": DOC, "ops": ops})

# Create document first
r_doc = c.post("/tools/create_document", json={"name": "Kids Room", "background": "#F8F4F0"})
DOC = r_doc.json()["data"]["document_id"]
print(f"Doc: {DOC}")

# ── 1. ROOM STRUCTURE ──
batch([
    {"tool": "create_region", "outline": [[0.0,0.0],[1.0,0.0],[1.0,0.55],[0.0,0.55]],
     "region_id": "wall_top", "fill": "#E8E0D8", "z_index": 0},
    {"tool": "create_region", "outline": [[0.0,0.55],[1.0,0.55],[1.0,0.72],[0.0,0.72]],
     "region_id": "wall_bot", "fill": "#D8D0C8", "z_index": 0},
    {"tool": "create_region", "outline": [[0.0,0.72],[1.0,0.72],[1.0,0.98],[0.0,0.98]],
     "region_id": "floor", "fill": "#C4A882", "z_index": 0},
    {"tool": "create_region", "outline": [[0.0,0.72],[1.0,0.72],[1.0,0.74],[0.0,0.74]],
     "region_id": "baseboard", "fill": "#FFF", "z_index": 1},
])
print("1. Room structure ✅")

# ── 2. WINDOW (right wall, with curtains) ──
batch([
    {"tool": "create_region",
     "outline": [[0.08,0.08],[0.35,0.08],[0.35,0.48],[0.08,0.48]],
     "region_id": "win_frame", "fill": "#D4C8B8", "stroke": "#8B7D6B", "stroke_width": 0.006, "z_index": 1},
    {"tool": "create_region",
     "outline": [[0.11,0.11],[0.32,0.11],[0.32,0.45],[0.11,0.45]],
     "region_id": "win_glass", "fill": "#B5D8E8", "z_index": 2},
    {"tool": "create_region",
     "outline": [[0.215,0.11],[0.225,0.11],[0.225,0.45],[0.215,0.45]],
     "region_id": "win_bar_v", "fill": "#C0B0A0", "z_index": 3},
    {"tool": "create_region",
     "outline": [[0.11,0.28],[0.32,0.28],[0.32,0.29],[0.11,0.29]],
     "region_id": "win_bar_h", "fill": "#C0B0A0", "z_index": 3},
    # Curtains
    {"tool": "create_region",
     "outline": [[0.04,0.06],[0.10,0.06],[0.10,0.50],[0.04,0.50]],
     "region_id": "curtain_l", "fill": "#6B8EC4", "opacity": 0.7, "z_index": 1},
    {"tool": "create_region",
     "outline": [[0.33,0.06],[0.39,0.06],[0.39,0.50],[0.33,0.50]],
     "region_id": "curtain_r", "fill": "#6B8EC4", "opacity": 0.7, "z_index": 1},
])
print("2. Window ✅")

# ── 3. BED (left side, colorful) ──
batch([
    {"tool": "create_region",
     "outline": [[0.55,0.42],[0.95,0.42],[0.95,0.70],[0.55,0.70]],
     "region_id": "bed_frame", "fill": "#A09080", "z_index": 2},
    {"tool": "create_region",
     "outline": [[0.57,0.44],[0.93,0.44],[0.93,0.66],[0.57,0.66]],
     "region_id": "mattress", "fill": "#F0E8E0", "z_index": 3},
    {"tool": "create_region",
     "outline": [[0.57,0.48],[0.93,0.48],[0.93,0.65],[0.57,0.65]],
     "region_id": "blanket", "fill": "#4A9EC4", "z_index": 4},
    # Pillows
    {"tool": "create_region",
     "outline": [[0.58,0.44],[0.66,0.44],[0.67,0.50],[0.57,0.50]],
     "region_id": "pillow_l", "fill": "#FFF", "z_index": 5},
    {"tool": "create_region",
     "outline": [[0.68,0.44],[0.76,0.44],[0.77,0.50],[0.67,0.50]],
     "region_id": "pillow_r", "fill": "#FFF", "z_index": 5},
])
print("3. Bed ✅")

# ── 4. RUG (playful shape) ──
r("rug", [[0.10,0.76],[0.28,0.74],[0.50,0.73],[0.72,0.74],[0.90,0.76],
          [0.72,0.80],[0.50,0.82],[0.28,0.80]],
  0.7, True, "#E8A060", z=2, op=0.8)
r("rug_stripe1", [[0.20,0.75],[0.30,0.74],[0.30,0.80],[0.20,0.79]],
  0.3, True, "#D08040", z=3, op=0.5)
r("rug_stripe2", [[0.45,0.735],[0.55,0.735],[0.55,0.81],[0.45,0.80]],
  0.3, True, "#D08040", z=3, op=0.5)
r("rug_stripe3", [[0.70,0.74],[0.80,0.75],[0.80,0.79],[0.70,0.78]],
  0.3, True, "#D08040", z=3, op=0.5)
print("4. Rug ✅")

# ── 5. TOYS / DECORATIONS ──
# Toy blocks on floor
batch([
    {"tool": "create_region", "outline": [[0.38,0.82],[0.44,0.82],[0.44,0.88],[0.38,0.88]],
     "region_id": "block1", "fill": "#E85450", "z_index": 5},
    {"tool": "create_region", "outline": [[0.44,0.84],[0.50,0.84],[0.50,0.88],[0.44,0.88]],
     "region_id": "block2", "fill": "#50B8E8", "z_index": 5},
    {"tool": "create_region", "outline": [[0.41,0.80],[0.47,0.80],[0.47,0.84],[0.41,0.84]],
     "region_id": "block3", "fill": "#F0D050", "z_index": 5},
])
# Star decoration on wall
r("star", [[0.50,0.15],[0.505,0.12],[0.51,0.15],[0.515,0.12],[0.52,0.15],[0.518,0.18],
           [0.52,0.20],[0.515,0.18],[0.51,0.20],[0.505,0.18]],
  0, True, "#F0D050", z=1)
# Picture frame on wall
batch([
    {"tool": "create_region", "outline": [[0.55,0.10],[0.70,0.10],[0.70,0.25],[0.55,0.25]],
     "region_id": "pic_frame", "fill": "#D4C8B8", "stroke": "#8B7D6B", "stroke_width": 0.004, "z_index": 1},
    {"tool": "create_region", "outline": [[0.57,0.12],[0.68,0.12],[0.68,0.23],[0.57,0.23]],
     "region_id": "pic_art", "fill": "#FFE8A0", "z_index": 2},
])
print("5. Decorations ✅")

# ── 6. LAMP / CEILING LIGHT ──
batch([
    {"tool": "create_region", "outline": [[0.495,0.0],[0.505,0.0],[0.505,0.04],[0.495,0.04]],
     "region_id": "lamp_wire", "fill": "#333", "z_index": 5},
    {"tool": "create_region", "outline": [[0.46,0.04],[0.54,0.04],[0.52,0.10],[0.48,0.10]],
     "region_id": "lamp_shade", "fill": "#F0E8D0", "z_index": 5},
    {"tool": "create_region", "outline": [[0.47,0.04],[0.53,0.04],[0.53,0.05],[0.47,0.05]],
     "region_id": "lamp_top", "fill": "#D4C8B8", "z_index": 6},
])
print("6. Lamp ✅")

# Describe
d = c.post("/tools/describe_scene", json={"document_id": DOC}).json()
print(f"\nTotal: {d['region_count']} regions")

# Render
r = c.post("/tools/render_preview", json={"document_id": DOC, "scale": 0.5}).json()
b64 = r["data"]["preview"].split("base64,")[1]
pad = 4 - len(b64) % 4
if pad != 4: b64 += "=" * pad
open("/Users/muhammadasif/Desktop/codes/avge/output/kids_room.png", "wb").write(base64.b64decode(b64))
print(f"Saved: kids_room.png")
print(f"Preview: http://localhost:8000/preview/{DOC}.png")
