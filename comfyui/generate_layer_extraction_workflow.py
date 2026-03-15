"""Generate layer extraction workflow using SAM for Inochi2D rigging.

Takes a reference character image and segments it into layers:
- Head/face base
- Eyes (left, right)
- Eyebrows
- Mouth
- Hair (back, front)
- Body

Uses Segment Anything Model (SAM) with point prompts to isolate each part.

Requirements:
  - ComfyUI-segment-anything extension
  - SAM model (sam_vit_h_4b8939.pth or sam_vit_b)

Run:  python comfyui/generate_layer_extraction_workflow.py
"""
import json

# ═══════════════════════════════════════════════════════════════════════
# LAYER DEFINITIONS
# Each layer has: name, approximate point prompts (x, y as % of image)
# Points tell SAM "this is what I want to segment"
# You'll need to adjust these based on your character
# ═══════════════════════════════════════════════════════════════════════

# For a 1024x1024 centered character, approximate positions:
LAYERS = [
    # (name, [(x%, y%), ...] positive points, [(x%, y%), ...] negative points)
    ("eye_left",      [(35, 35)], [(50, 35), (20, 35)]),  # left eye
    ("eye_right",     [(65, 35)], [(50, 35), (80, 35)]),  # right eye
    ("eyebrow_left",  [(35, 30)], [(35, 35), (50, 30)]),  # left brow
    ("eyebrow_right", [(65, 30)], [(65, 35), (50, 30)]),  # right brow
    ("mouth",         [(50, 55)], [(50, 35), (50, 70)]),  # mouth
    ("nose",          [(50, 45)], [(50, 35), (50, 55)]),  # nose (optional)
    ("hair_front",    [(50, 15)], [(50, 50)]),            # bangs
    ("hair_back",     [(50, 10)], [(50, 40)]),            # back hair
    ("face_base",     [(50, 40)], [(50, 10), (50, 80)]),  # face shape
]

# Image size (should match your reference)
IMG_SIZE = 1024

nodes = []
links = []
link_id = 0
node_idx = {}

def L():
    global link_id
    link_id += 1
    return link_id

def add(node):
    node_idx[node["id"]] = len(nodes)
    nodes.append(node)

def out_links(nid, slot=0):
    return nodes[node_idx[nid]]["outputs"][slot]["links"]

# ═══════════════════════════════════════════════════════════════════════
# SHARED NODES
# ═══════════════════════════════════════════════════════════════════════

# 1: LoadImage (reference character)
add({
    "id": 1, "type": "LoadImage",
    "pos": [-400, 0], "size": [315, 400],
    "properties": {},
    "widgets_values": ["mira_reference.png", "image"],
    "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
    ],
    "title": "Load Reference Character"
})

# 2: SAMModelLoader
add({
    "id": 2, "type": "SAMModelLoader",
    "pos": [-400, 450], "size": [315, 58],
    "properties": {},
    "widgets_values": ["sam_vit_h_4b8939.pth", "cuda"],
    "outputs": [{"name": "SAM_MODEL", "type": "SAM_MODEL", "links": [], "slot_index": 0}],
    "title": "Load SAM Model"
})

# ═══════════════════════════════════════════════════════════════════════
# PER-LAYER SEGMENTATION
# Each layer: SAMPredictor → mask → composite with transparency → save
# ═══════════════════════════════════════════════════════════════════════

ROW_H = 200
START_Y = -100

for i, (name, pos_points, neg_points) in enumerate(LAYERS):
    y = START_Y + i * ROW_H
    
    sam_id = 10 + i * 10      # SAMPredictor
    mask_id = 11 + i * 10     # Convert mask
    comp_id = 12 + i * 10     # JoinImageWithAlpha
    save_id = 13 + i * 10     # SaveImage
    
    # Convert percentage points to pixel coords
    pos_coords = [[int(x * IMG_SIZE / 100), int(y * IMG_SIZE / 100)] for x, y in pos_points]
    neg_coords = [[int(x * IMG_SIZE / 100), int(y * IMG_SIZE / 100)] for x, y in neg_points]
    
    # Format for SAM: "x1,y1;x2,y2" positive and negative
    pos_str = ";".join(f"{p[0]},{p[1]}" for p in pos_coords)
    neg_str = ";".join(f"{p[0]},{p[1]}" for p in neg_coords) if neg_coords else ""
    
    # Links for this layer
    l_img_sam = L()
    l_sam_model = L()
    l_img_comp = L()
    l_mask_comp = L()
    l_comp_save = L()
    
    # SAMPredictor (segment based on points)
    add({
        "id": sam_id, "type": "SAMPredictor",
        "pos": [0, y], "size": [350, 130],
        "properties": {},
        "widgets_values": [pos_str, neg_str, 0.5],  # positive, negative, threshold
        "inputs": [
            {"name": "sam_model", "type": "SAM_MODEL", "link": l_sam_model},
            {"name": "image", "type": "IMAGE", "link": l_img_sam},
        ],
        "outputs": [
            {"name": "MASK", "type": "MASK", "links": [], "slot_index": 0},
        ],
        "title": f"Segment: {name}"
    })
    links.append([l_img_sam, 1, 0, sam_id, 1, "IMAGE"])
    links.append([l_sam_model, 2, 0, sam_id, 0, "SAM_MODEL"])
    out_links(1, 0).append(l_img_sam)
    out_links(2, 0).append(l_sam_model)
    
    # JoinImageWithAlpha (apply mask as alpha channel)
    add({
        "id": comp_id, "type": "JoinImageWithAlpha",
        "pos": [400, y], "size": [200, 50],
        "properties": {},
        "widgets_values": [],
        "inputs": [
            {"name": "image", "type": "IMAGE", "link": l_img_comp},
            {"name": "alpha", "type": "MASK", "link": l_mask_comp},
        ],
        "outputs": [
            {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        ],
        "title": f"Add Alpha: {name}"
    })
    links.append([l_img_comp, 1, 0, comp_id, 0, "IMAGE"])
    links.append([l_mask_comp, sam_id, 0, comp_id, 1, "MASK"])
    out_links(1, 0).append(l_img_comp)
    out_links(sam_id, 0).append(l_mask_comp)
    
    # SaveImage (PNG with transparency)
    add({
        "id": save_id, "type": "SaveImage",
        "pos": [650, y - 50], "size": [300, 250],
        "properties": {},
        "widgets_values": [f"mira_layer_{name}"],
        "inputs": [{"name": "images", "type": "IMAGE", "link": l_comp_save}],
        "title": f"Save: {name}"
    })
    links.append([l_comp_save, comp_id, 0, save_id, 0, "IMAGE"])
    out_links(comp_id, 0).append(l_comp_save)

# ═══════════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════════

NOTE_TEXT = """=== LAYER EXTRACTION FOR INOCHI2D ===

This workflow uses SAM (Segment Anything) to extract layers
from your character reference for Inochi2D rigging.

REQUIREMENTS:
  - ComfyUI-segment-anything extension
  - SAM model: sam_vit_h_4b8939.pth in models/sams/

HOW TO USE:
1. Load your reference character image
2. Adjust point coordinates in each SAMPredictor node:
   - Positive points: click ON the part you want
   - Negative points: click on nearby parts you DON'T want
3. Run workflow - each layer saved as PNG with transparency

POINT COORDINATES:
  Points are in format "x,y" or "x1,y1;x2,y2" for multiple
  For 1024x1024 image:
  - Center: 512,512
  - Left eye (approx): 360,360
  - Right eye (approx): 660,360
  - Mouth: 512,560

TIPS:
  - Start with one layer, get it right, then do others
  - More points = more precise selection
  - Negative points help exclude nearby parts
  - May need manual cleanup in Photoshop/GIMP

OUTPUT FILES:
  mira_layer_eye_left.png
  mira_layer_eye_right.png
  mira_layer_eyebrow_left.png
  mira_layer_eyebrow_right.png
  mira_layer_mouth.png
  mira_layer_hair_front.png
  mira_layer_hair_back.png
  mira_layer_face_base.png

NEXT STEPS:
  1. Import layers into Inochi2D
  2. Create hierarchy (eyes → head, mouth → head, etc.)
  3. Add mesh deformation
  4. Define parameters for animation
"""

add({
    "id": 100, "type": "Note",
    "pos": [-400, 550], "size": [500, 500],
    "properties": {},
    "widgets_values": [NOTE_TEXT],
    "title": "Instructions"
})

# Alternative manual extraction note
MANUAL_NOTE = """=== MANUAL EXTRACTION (BACKUP) ===

If SAM doesn't segment cleanly, do it manually:

1. Open reference in Photoshop/GIMP
2. Select each part with lasso/magic wand
3. Copy to new layer
4. Delete background (transparent)
5. Save each layer as PNG

Keep all layers same canvas size (1024x1024)
so they align when stacked in Inochi2D.
"""

add({
    "id": 101, "type": "Note",
    "pos": [650, 1600], "size": [350, 250],
    "properties": {},
    "widgets_values": [MANUAL_NOTE],
    "title": "Fallback: Manual Extraction"
})

# ═══════════════════════════════════════════════════════════════════════
# ASSEMBLE
# ═══════════════════════════════════════════════════════════════════════

workflow = {
    "last_node_id": max(n["id"] for n in nodes),
    "last_link_id": link_id,
    "nodes": nodes,
    "links": links,
    "groups": [
        {"title": "Input", "bounding": [-420, -50, 360, 550], "color": "#3f789e"},
        {"title": "Layer Extraction", "bounding": [-20, -150, 980, len(LAYERS) * ROW_H + 100], "color": "#8e6f3f"},
    ],
    "config": {},
    "extra": {},
    "version": 0.4,
}

out_path = __file__.replace("generate_layer_extraction_workflow.py", "mira_layer_extraction.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"  {len(nodes)} nodes, {link_id} links")
print(f"  Layers: {[l[0] for l in LAYERS]}")
