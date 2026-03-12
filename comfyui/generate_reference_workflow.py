"""Generate the Flux reference workflow with crop option.

Adds ImageCrop node after VAEDecode to extract head region from full-body generations.
Also saves the full image for reference.

Run:  python comfyui/generate_reference_workflow.py
"""
import json

# ═══════════════════════════════════════════════════════════════════════
# CROP SETTINGS - Adjust these for your character
# ═══════════════════════════════════════════════════════════════════════
# For a 1024x1024 full body, head is typically in upper third
# Adjust x, y, width, height based on your generations

CROP_X = 256       # Left edge of crop (0 = left side of image)
CROP_Y = 0         # Top edge of crop (0 = top of image)
CROP_WIDTH = 512   # Width of cropped region
CROP_HEIGHT = 512  # Height of cropped region

# Generation settings
GEN_WIDTH = 1024
GEN_HEIGHT = 1024

# ═══════════════════════════════════════════════════════════════════════
# STYLE PROMPT - Customize for your character
# ═══════════════════════════════════════════════════════════════════════
STYLE_PROMPT = """\
anime, cyberpunk, cyborg, exosuit, armor, 1girl, solo, 
looking straight at viewer, closed mouth, white hair, bob cut, 
glowing, robot, glowing eyes, futuristic, sci-fi, 
blush, short hair, purple eyes, 
anime artwork retro cyberpunk anime art by Tsubasa Nakai, 
Painting, Hyperrealism, detailed, 80's inspired, synthwave, neon, vibrant, 
retro futurism, anime style, key visual, studio anime, highly detailed, 
big expressive eyes, black background, 
front view, centered, full body, standing pose, arms at sides\
"""

# For face-only (alternative prompt)
FACE_ONLY_PROMPT = """\
anime, cyberpunk, cyborg, 1girl, solo, 
looking straight at viewer, closed mouth, white hair, bob cut, 
glowing eyes, futuristic, sci-fi, blush, purple eyes, 
anime style, highly detailed, big expressive eyes, 
black background, front view, centered, 
portrait, face only, head shot, shoulders up, 
no hands visible, close up face\
"""

# ═══════════════════════════════════════════════════════════════════════
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
# MODEL LOADING
# ═══════════════════════════════════════════════════════════════════════

# 1: UNETLoader
add({
    "id": 1, "type": "UNETLoader",
    "pos": [-600, -200], "size": [315, 82],
    "properties": {"Node name for S&R": "UNETLoader"},
    "widgets_values": ["flux_dev.safetensors", "default"],
    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
    "title": "Flux UNET"
})

# 2: DualCLIPLoader
add({
    "id": 2, "type": "DualCLIPLoader",
    "pos": [-600, -70], "size": [315, 130],
    "properties": {"Node name for S&R": "DualCLIPLoader"},
    "widgets_values": ["t5xxl_fp16.safetensors", "clip_l.safetensors", "flux", "default"],
    "outputs": [{"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 0}],
    "title": "Dual CLIP"
})

# 3: VAELoader
add({
    "id": 3, "type": "VAELoader",
    "pos": [-600, 120], "size": [315, 58],
    "properties": {"Node name for S&R": "VAELoader"},
    "widgets_values": ["ae.safetensors"],
    "outputs": [{"name": "VAE", "type": "VAE", "links": [], "slot_index": 0}],
    "title": "Flux VAE"
})

# 4: LoraLoader
l_unet_lora = L()
l_clip_lora = L()
add({
    "id": 4, "type": "LoraLoader",
    "pos": [-220, -200], "size": [315, 126],
    "properties": {"Node name for S&R": "LoraLoader"},
    "widgets_values": ["RM_Anime_Cyberpunk_v0.5M.safetensors", 1, 1],
    "inputs": [
        {"name": "model", "type": "MODEL", "link": l_unet_lora},
        {"name": "clip", "type": "CLIP", "link": l_clip_lora},
    ],
    "outputs": [
        {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
        {"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 1},
    ],
    "title": "LoRA (style)"
})
links.append([l_unet_lora, 1, 0, 4, 0, "MODEL"])
links.append([l_clip_lora, 2, 0, 4, 1, "CLIP"])
out_links(1).append(l_unet_lora)
out_links(2).append(l_clip_lora)

# ═══════════════════════════════════════════════════════════════════════
# PROMPT
# ═══════════════════════════════════════════════════════════════════════

# 5: CLIPTextEncode (positive)
l_clip_prompt = L()
add({
    "id": 5, "type": "CLIPTextEncode",
    "pos": [150, -300], "size": [450, 200],
    "properties": {"Node name for S&R": "CLIPTextEncode"},
    "widgets_values": [STYLE_PROMPT],
    "inputs": [{"name": "clip", "type": "CLIP", "link": l_clip_prompt}],
    "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}],
    "title": "Positive Prompt (EDIT HERE)"
})
links.append([l_clip_prompt, 4, 1, 5, 0, "CLIP"])
out_links(4, 1).append(l_clip_prompt)

# 6: FluxGuidance
l_cond_guid = L()
add({
    "id": 6, "type": "FluxGuidance",
    "pos": [650, -250], "size": [280, 58],
    "properties": {"Node name for S&R": "FluxGuidance"},
    "widgets_values": [3.5],
    "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": l_cond_guid}],
    "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}],
    "title": "Guidance (3.5)"
})
links.append([l_cond_guid, 5, 0, 6, 0, "CONDITIONING"])
out_links(5).append(l_cond_guid)

# ═══════════════════════════════════════════════════════════════════════
# SAMPLING SETUP
# ═══════════════════════════════════════════════════════════════════════

# 7: ModelSamplingFlux
l_model_msf = L()
add({
    "id": 7, "type": "ModelSamplingFlux",
    "pos": [150, 0], "size": [315, 130],
    "properties": {"Node name for S&R": "ModelSamplingFlux"},
    "widgets_values": [1.15, 0.5, GEN_WIDTH, GEN_HEIGHT],
    "inputs": [{"name": "model", "type": "MODEL", "link": l_model_msf}],
    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
    "title": "ModelSamplingFlux"
})
links.append([l_model_msf, 4, 0, 7, 0, "MODEL"])
out_links(4, 0).append(l_model_msf)

# 8: BasicGuider
l_model_guider = L()
l_cond_guider = L()
add({
    "id": 8, "type": "BasicGuider",
    "pos": [650, -150], "size": [222, 46],
    "properties": {"Node name for S&R": "BasicGuider"},
    "widgets_values": [],
    "inputs": [
        {"name": "model", "type": "MODEL", "link": l_model_guider},
        {"name": "conditioning", "type": "CONDITIONING", "link": l_cond_guider},
    ],
    "outputs": [{"name": "GUIDER", "type": "GUIDER", "links": [], "slot_index": 0}],
    "title": "BasicGuider"
})
links.append([l_model_guider, 7, 0, 8, 0, "MODEL"])
links.append([l_cond_guider, 6, 0, 8, 1, "CONDITIONING"])
out_links(7).append(l_model_guider)
out_links(6).append(l_cond_guider)

# 9: RandomNoise
add({
    "id": 9, "type": "RandomNoise",
    "pos": [650, 0], "size": [315, 82],
    "properties": {"Node name for S&R": "RandomNoise"},
    "widgets_values": [42, "randomize"],  # Change to "fixed" for consistency
    "outputs": [{"name": "NOISE", "type": "NOISE", "links": [], "slot_index": 0}],
    "title": "Noise (randomize for exploration)"
})

# 10: KSamplerSelect
add({
    "id": 10, "type": "KSamplerSelect",
    "pos": [650, 130], "size": [315, 58],
    "properties": {"Node name for S&R": "KSamplerSelect"},
    "widgets_values": ["euler"],
    "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "links": [], "slot_index": 0}],
    "title": "Sampler (euler)"
})

# 11: BasicScheduler
l_model_sched = L()
add({
    "id": 11, "type": "BasicScheduler",
    "pos": [650, 230], "size": [315, 106],
    "properties": {"Node name for S&R": "BasicScheduler"},
    "widgets_values": ["simple", 30, 1],
    "inputs": [{"name": "model", "type": "MODEL", "link": l_model_sched}],
    "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "links": [], "slot_index": 0}],
    "title": "Scheduler (30 steps)"
})
links.append([l_model_sched, 7, 0, 11, 0, "MODEL"])
out_links(7).append(l_model_sched)

# 12: EmptySD3LatentImage
add({
    "id": 12, "type": "EmptySD3LatentImage",
    "pos": [650, 380], "size": [315, 106],
    "properties": {"Node name for S&R": "EmptySD3LatentImage"},
    "widgets_values": [GEN_WIDTH, GEN_HEIGHT, 1],
    "outputs": [{"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}],
    "title": f"Empty Latent ({GEN_WIDTH}x{GEN_HEIGHT})"
})

# ═══════════════════════════════════════════════════════════════════════
# SAMPLER + DECODE
# ═══════════════════════════════════════════════════════════════════════

# 13: SamplerCustomAdvanced
l_noise = L()
l_guider = L()
l_sampler = L()
l_sigmas = L()
l_latent = L()
add({
    "id": 13, "type": "SamplerCustomAdvanced",
    "pos": [1050, 0], "size": [272, 180],
    "properties": {"Node name for S&R": "SamplerCustomAdvanced"},
    "widgets_values": [],
    "inputs": [
        {"name": "noise", "type": "NOISE", "link": l_noise},
        {"name": "guider", "type": "GUIDER", "link": l_guider},
        {"name": "sampler", "type": "SAMPLER", "link": l_sampler},
        {"name": "sigmas", "type": "SIGMAS", "link": l_sigmas},
        {"name": "latent_image", "type": "LATENT", "link": l_latent},
    ],
    "outputs": [
        {"name": "output", "type": "LATENT", "links": [], "slot_index": 0},
        {"name": "denoised_output", "type": "LATENT", "links": [], "slot_index": 1},
    ],
    "title": "SamplerCustomAdvanced"
})
links.append([l_noise, 9, 0, 13, 0, "NOISE"])
links.append([l_guider, 8, 0, 13, 1, "GUIDER"])
links.append([l_sampler, 10, 0, 13, 2, "SAMPLER"])
links.append([l_sigmas, 11, 0, 13, 3, "SIGMAS"])
links.append([l_latent, 12, 0, 13, 4, "LATENT"])
out_links(9).append(l_noise)
out_links(8).append(l_guider)
out_links(10).append(l_sampler)
out_links(11).append(l_sigmas)
out_links(12).append(l_latent)

# 14: VAEDecode
l_samples = L()
l_vae = L()
add({
    "id": 14, "type": "VAEDecode",
    "pos": [1400, 50], "size": [210, 46],
    "properties": {"Node name for S&R": "VAEDecode"},
    "widgets_values": [],
    "inputs": [
        {"name": "samples", "type": "LATENT", "link": l_samples},
        {"name": "vae", "type": "VAE", "link": l_vae},
    ],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
})
links.append([l_samples, 13, 0, 14, 0, "LATENT"])
links.append([l_vae, 3, 0, 14, 1, "VAE"])
out_links(13, 0).append(l_samples)
out_links(3).append(l_vae)

# ═══════════════════════════════════════════════════════════════════════
# OUTPUT: FULL IMAGE
# ═══════════════════════════════════════════════════════════════════════

# 15: SaveImage (full)
l_img_full = L()
add({
    "id": 15, "type": "SaveImage",
    "pos": [1700, -200], "size": [400, 400],
    "properties": {"Node name for S&R": "SaveImage"},
    "widgets_values": ["pii-chan_full"],
    "inputs": [{"name": "images", "type": "IMAGE", "link": l_img_full}],
    "title": "Save FULL Image"
})
links.append([l_img_full, 14, 0, 15, 0, "IMAGE"])
out_links(14).append(l_img_full)

# ═══════════════════════════════════════════════════════════════════════
# OUTPUT: CROPPED HEAD
# ═══════════════════════════════════════════════════════════════════════

# 16: ImageCrop
l_img_crop = L()
add({
    "id": 16, "type": "ImageCrop",
    "pos": [1700, 250], "size": [315, 130],
    "properties": {"Node name for S&R": "ImageCrop"},
    "widgets_values": [CROP_WIDTH, CROP_HEIGHT, CROP_X, CROP_Y],
    "inputs": [{"name": "image", "type": "IMAGE", "link": l_img_crop}],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
    "title": f"Crop Head ({CROP_WIDTH}x{CROP_HEIGHT} at {CROP_X},{CROP_Y})"
})
links.append([l_img_crop, 14, 0, 16, 0, "IMAGE"])
out_links(14).append(l_img_crop)

# 17: SaveImage (cropped)
l_img_save_crop = L()
add({
    "id": 17, "type": "SaveImage",
    "pos": [2100, 200], "size": [400, 400],
    "properties": {"Node name for S&R": "SaveImage"},
    "widgets_values": ["pii-chan_head"],
    "inputs": [{"name": "images", "type": "IMAGE", "link": l_img_save_crop}],
    "title": "Save CROPPED Head"
})
links.append([l_img_save_crop, 16, 0, 17, 0, "IMAGE"])
out_links(16).append(l_img_save_crop)

# ═══════════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════════

NOTE_TEXT = f"""=== PII-CHAN REFERENCE GENERATOR ===

This workflow generates a reference character and saves:
1. FULL IMAGE - for Inochi2D rigging (full body)
2. CROPPED HEAD - for face-only display

CROP SETTINGS (adjust in ImageCrop node):
  X: {CROP_X}  Y: {CROP_Y}
  Width: {CROP_WIDTH}  Height: {CROP_HEIGHT}

For centered character in 1024x1024:
- Head at top center: X=256, Y=0, 512x512
- Upper body: X=128, Y=0, 768x768
- Just face: X=320, Y=64, 384x384

WORKFLOW:
1. Edit prompt for your character design
2. Generate (randomize seed to explore)
3. Find a good one? Set seed to "fixed"
4. Adjust crop position if needed
5. Use full image for Inochi2D rigging
6. Use cropped head as display reference

OUTPUTS:
- pii-chan_full_*.png   → Full body for rigging
- pii-chan_head_*.png   → Cropped head for face display
"""

add({
    "id": 18, "type": "Note",
    "pos": [-600, 300], "size": [500, 400],
    "properties": {},
    "widgets_values": [NOTE_TEXT],
    "title": "Instructions"
})

# Face-only prompt note
add({
    "id": 19, "type": "Note",
    "pos": [150, -550], "size": [450, 180],
    "properties": {},
    "widgets_values": [f"ALTERNATIVE FACE-ONLY PROMPT:\n\n{FACE_ONLY_PROMPT}"],
    "title": "Face-Only Prompt (copy if needed)"
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
        {"title": "Model Loading", "bounding": [-620, -240, 720, 430], "color": "#3f789e"},
        {"title": "Prompt", "bounding": [130, -580, 480, 520], "color": "#3f8e5e"},
        {"title": "Sampling", "bounding": [630, -280, 340, 720], "color": "#5e3f8e"},
        {"title": "Output", "bounding": [1680, -240, 860, 700], "color": "#8e6f3f"},
    ],
    "config": {},
    "extra": {},
    "version": 0.4,
}

out_path = __file__.replace("generate_reference_workflow.py", "pii-chan_flux_reference_v2.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"  {len(nodes)} nodes, {link_id} links")
print(f"  Crop: {CROP_WIDTH}x{CROP_HEIGHT} at ({CROP_X}, {CROP_Y})")
