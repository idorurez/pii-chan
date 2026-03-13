"""Generate the Flux reference workflow with ControlNet Pose for T-pose.

Uses InstantX FLUX.1-dev-Controlnet-Union (mode 4 = pose) to force T-pose.
Feed it a T-pose skeleton image and it will follow the pose.

Requirements:
  - ComfyUI-Flux-ControlNet or similar extension supporting InstantX Union
  - InstantX/FLUX.1-dev-Controlnet-Union model
  - A T-pose skeleton/silhouette image

Run:  python comfyui/generate_reference_controlnet_workflow.py
"""
import json

# ═══════════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════════

# Generation settings
GEN_WIDTH = 1024
GEN_HEIGHT = 1024

# Crop settings (for head extraction)
CROP_X = 256
CROP_Y = 0
CROP_WIDTH = 512
CROP_HEIGHT = 512

# ControlNet settings
CONTROLNET_STRENGTH = 0.7  # 0.5-0.8 works well, higher = stricter pose adherence
CONTROL_MODE = 4  # 0=canny, 1=tile, 2=depth, 3=blur, 4=pose, 5=gray, 6=lq

# ═══════════════════════════════════════════════════════════════════════
# PROMPTS
# ═══════════════════════════════════════════════════════════════════════

STYLE_PROMPT = """\
anime, cyberpunk, cyborg, tight fitting exosuit, armor, 1girl, solo, 
looking straight at viewer, closed mouth, white hair, bob cut, face markings,
robot, glowing eyes, futuristic, sci-fi, blush, short hair, dark purple eyes, purple glow,
anime artwork retro cyberpunk anime art by Tsubasa Nakai, 
Painting, Hyperrealism, detailed, 80's inspired, synthwave, neon, vibrant, 
retro futurism, anime style, key visual, studio anime, highly detailed, 
big expressive eyes, black background, 
full body, front view, centered, symmetrical pose,
even flat lighting, character reference sheet style\
"""

# Note: Pose is controlled by ControlNet, not prompt keywords

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

# 1: UNETLoader (Flux)
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
# CONTROLNET (POSE)
# ═══════════════════════════════════════════════════════════════════════

# 5: Load ControlNet Union model
add({
    "id": 5, "type": "ControlNetLoader",
    "pos": [-600, 250], "size": [315, 58],
    "properties": {"Node name for S&R": "ControlNetLoader"},
    "widgets_values": ["flux-controlnet-union.safetensors"],
    "outputs": [{"name": "CONTROL_NET", "type": "CONTROL_NET", "links": [], "slot_index": 0}],
    "title": "ControlNet Union (InstantX)"
})

# 6: Load T-pose reference image
add({
    "id": 6, "type": "LoadImage",
    "pos": [-600, 360], "size": [315, 400],
    "properties": {},
    "widgets_values": ["t-pose_skeleton.png", "image"],
    "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
        {"name": "MASK", "type": "MASK", "links": [], "slot_index": 1},
    ],
    "title": "T-Pose Reference (LOAD YOUR SKELETON)"
})

# 7: Apply ControlNet
l_cnet = L()
l_pose_img = L()
l_cond_in = L()
add({
    "id": 7, "type": "ControlNetApplyAdvanced",
    "pos": [150, 250], "size": [320, 180],
    "properties": {"Node name for S&R": "ControlNetApplyAdvanced"},
    "widgets_values": [CONTROLNET_STRENGTH, 0.0, 1.0],  # strength, start_percent, end_percent
    "inputs": [
        {"name": "positive", "type": "CONDITIONING", "link": l_cond_in},
        {"name": "negative", "type": "CONDITIONING", "link": None},
        {"name": "control_net", "type": "CONTROL_NET", "link": l_cnet},
        {"name": "image", "type": "IMAGE", "link": l_pose_img},
    ],
    "outputs": [
        {"name": "positive", "type": "CONDITIONING", "links": [], "slot_index": 0},
        {"name": "negative", "type": "CONDITIONING", "links": [], "slot_index": 1},
    ],
    "title": f"Apply ControlNet (strength={CONTROLNET_STRENGTH})"
})
links.append([l_cnet, 5, 0, 7, 2, "CONTROL_NET"])
links.append([l_pose_img, 6, 0, 7, 3, "IMAGE"])
out_links(5).append(l_cnet)
out_links(6, 0).append(l_pose_img)

# ═══════════════════════════════════════════════════════════════════════
# PROMPT
# ═══════════════════════════════════════════════════════════════════════

# 8: CLIPTextEncode (positive)
l_clip_prompt = L()
add({
    "id": 8, "type": "CLIPTextEncode",
    "pos": [150, -100], "size": [450, 200],
    "properties": {"Node name for S&R": "CLIPTextEncode"},
    "widgets_values": [STYLE_PROMPT],
    "inputs": [{"name": "clip", "type": "CLIP", "link": l_clip_prompt}],
    "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}],
    "title": "Positive Prompt (EDIT HERE)"
})
links.append([l_clip_prompt, 4, 1, 8, 0, "CLIP"])
out_links(4, 1).append(l_clip_prompt)

# Connect prompt to ControlNet input
links.append([l_cond_in, 8, 0, 7, 0, "CONDITIONING"])
out_links(8).append(l_cond_in)

# 9: FluxGuidance (after ControlNet)
l_cond_cnet = L()
add({
    "id": 9, "type": "FluxGuidance",
    "pos": [550, 250], "size": [280, 58],
    "properties": {"Node name for S&R": "FluxGuidance"},
    "widgets_values": [3.5],
    "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": l_cond_cnet}],
    "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}],
    "title": "Guidance (3.5)"
})
links.append([l_cond_cnet, 7, 0, 9, 0, "CONDITIONING"])
out_links(7, 0).append(l_cond_cnet)

# ═══════════════════════════════════════════════════════════════════════
# SAMPLING SETUP
# ═══════════════════════════════════════════════════════════════════════

# 10: ModelSamplingFlux
l_model_msf = L()
add({
    "id": 10, "type": "ModelSamplingFlux",
    "pos": [150, 80], "size": [315, 130],
    "properties": {"Node name for S&R": "ModelSamplingFlux"},
    "widgets_values": [1.15, 0.5, GEN_WIDTH, GEN_HEIGHT],
    "inputs": [{"name": "model", "type": "MODEL", "link": l_model_msf}],
    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
    "title": "ModelSamplingFlux"
})
links.append([l_model_msf, 4, 0, 10, 0, "MODEL"])
out_links(4, 0).append(l_model_msf)

# 11: BasicGuider
l_model_guider = L()
l_cond_guider = L()
add({
    "id": 11, "type": "BasicGuider",
    "pos": [900, 250], "size": [222, 46],
    "properties": {"Node name for S&R": "BasicGuider"},
    "widgets_values": [],
    "inputs": [
        {"name": "model", "type": "MODEL", "link": l_model_guider},
        {"name": "conditioning", "type": "CONDITIONING", "link": l_cond_guider},
    ],
    "outputs": [{"name": "GUIDER", "type": "GUIDER", "links": [], "slot_index": 0}],
    "title": "BasicGuider"
})
links.append([l_model_guider, 10, 0, 11, 0, "MODEL"])
links.append([l_cond_guider, 9, 0, 11, 1, "CONDITIONING"])
out_links(10).append(l_model_guider)
out_links(9).append(l_cond_guider)

# 12: RandomNoise
add({
    "id": 12, "type": "RandomNoise",
    "pos": [900, 350], "size": [315, 82],
    "properties": {"Node name for S&R": "RandomNoise"},
    "widgets_values": [42, "randomize"],
    "outputs": [{"name": "NOISE", "type": "NOISE", "links": [], "slot_index": 0}],
    "title": "Noise (randomize to explore)"
})

# 13: KSamplerSelect
add({
    "id": 13, "type": "KSamplerSelect",
    "pos": [900, 480], "size": [315, 58],
    "properties": {"Node name for S&R": "KSamplerSelect"},
    "widgets_values": ["euler"],
    "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "links": [], "slot_index": 0}],
    "title": "Sampler (euler)"
})

# 14: BasicScheduler
l_model_sched = L()
add({
    "id": 14, "type": "BasicScheduler",
    "pos": [900, 580], "size": [315, 106],
    "properties": {"Node name for S&R": "BasicScheduler"},
    "widgets_values": ["simple", 30, 1],
    "inputs": [{"name": "model", "type": "MODEL", "link": l_model_sched}],
    "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "links": [], "slot_index": 0}],
    "title": "Scheduler (30 steps)"
})
links.append([l_model_sched, 10, 0, 14, 0, "MODEL"])
out_links(10).append(l_model_sched)

# 15: EmptySD3LatentImage
add({
    "id": 15, "type": "EmptySD3LatentImage",
    "pos": [900, 730], "size": [315, 106],
    "properties": {"Node name for S&R": "EmptySD3LatentImage"},
    "widgets_values": [GEN_WIDTH, GEN_HEIGHT, 1],
    "outputs": [{"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}],
    "title": f"Empty Latent ({GEN_WIDTH}x{GEN_HEIGHT})"
})

# ═══════════════════════════════════════════════════════════════════════
# SAMPLER + DECODE
# ═══════════════════════════════════════════════════════════════════════

# 16: SamplerCustomAdvanced
l_noise = L()
l_guider = L()
l_sampler = L()
l_sigmas = L()
l_latent = L()
add({
    "id": 16, "type": "SamplerCustomAdvanced",
    "pos": [1300, 400], "size": [272, 180],
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
links.append([l_noise, 12, 0, 16, 0, "NOISE"])
links.append([l_guider, 11, 0, 16, 1, "GUIDER"])
links.append([l_sampler, 13, 0, 16, 2, "SAMPLER"])
links.append([l_sigmas, 14, 0, 16, 3, "SIGMAS"])
links.append([l_latent, 15, 0, 16, 4, "LATENT"])
out_links(12).append(l_noise)
out_links(11).append(l_guider)
out_links(13).append(l_sampler)
out_links(14).append(l_sigmas)
out_links(15).append(l_latent)

# 17: VAEDecode
l_samples = L()
l_vae = L()
add({
    "id": 17, "type": "VAEDecode",
    "pos": [1650, 450], "size": [210, 46],
    "properties": {"Node name for S&R": "VAEDecode"},
    "widgets_values": [],
    "inputs": [
        {"name": "samples", "type": "LATENT", "link": l_samples},
        {"name": "vae", "type": "VAE", "link": l_vae},
    ],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
})
links.append([l_samples, 16, 0, 17, 0, "LATENT"])
links.append([l_vae, 3, 0, 17, 1, "VAE"])
out_links(16, 0).append(l_samples)
out_links(3).append(l_vae)

# ═══════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════

# 18: SaveImage (full)
l_img_full = L()
add({
    "id": 18, "type": "SaveImage",
    "pos": [1950, 200], "size": [400, 400],
    "properties": {"Node name for S&R": "SaveImage"},
    "widgets_values": ["pii-chan_tpose_full"],
    "inputs": [{"name": "images", "type": "IMAGE", "link": l_img_full}],
    "title": "Save FULL T-Pose Image"
})
links.append([l_img_full, 17, 0, 18, 0, "IMAGE"])
out_links(17).append(l_img_full)

# 19: ImageCrop
l_img_crop = L()
add({
    "id": 19, "type": "ImageCrop",
    "pos": [1950, 650], "size": [315, 130],
    "properties": {"Node name for S&R": "ImageCrop"},
    "widgets_values": [CROP_WIDTH, CROP_HEIGHT, CROP_X, CROP_Y],
    "inputs": [{"name": "image", "type": "IMAGE", "link": l_img_crop}],
    "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0}],
    "title": f"Crop Head ({CROP_WIDTH}x{CROP_HEIGHT})"
})
links.append([l_img_crop, 17, 0, 19, 0, "IMAGE"])
out_links(17).append(l_img_crop)

# 20: SaveImage (cropped)
l_img_save_crop = L()
add({
    "id": 20, "type": "SaveImage",
    "pos": [2350, 600], "size": [400, 400],
    "properties": {"Node name for S&R": "SaveImage"},
    "widgets_values": ["pii-chan_tpose_head"],
    "inputs": [{"name": "images", "type": "IMAGE", "link": l_img_save_crop}],
    "title": "Save CROPPED Head"
})
links.append([l_img_save_crop, 19, 0, 20, 0, "IMAGE"])
out_links(19).append(l_img_save_crop)

# ═══════════════════════════════════════════════════════════════════════
# NOTES
# ═══════════════════════════════════════════════════════════════════════

NOTE_TEXT = f"""=== PII-CHAN T-POSE REFERENCE (ControlNet) ===

This workflow uses ControlNet to FORCE a T-pose or A-pose.
The pose comes from your reference skeleton image, not the prompt.

SETUP:
1. Download InstantX FLUX.1-dev-Controlnet-Union model:
   https://huggingface.co/InstantX/FLUX.1-dev-Controlnet-Union
   → Put in ComfyUI/models/controlnet/

2. Get a T-pose skeleton image (PNG, 1024x1024):
   - OpenPose skeleton
   - Simple stick figure
   - Silhouette in T-pose
   → Save as "t-pose_skeleton.png" in ComfyUI/input/

3. Install ControlNet nodes if needed:
   - ComfyUI-Advanced-ControlNet
   - Or x-flux-comfyui (XLabs)

CONTROL MODES (InstantX Union):
  0 = canny, 1 = tile, 2 = depth, 3 = blur
  4 = POSE (we use this), 5 = gray, 6 = lq

TUNING:
  - ControlNet strength: {CONTROLNET_STRENGTH} (0.5-0.8 recommended)
  - Higher = stricter pose adherence, less creative freedom
  - Lower = more artistic interpretation

OUTPUTS:
- pii-chan_tpose_full_*.png → Full body for Inochi2D rigging
- pii-chan_tpose_head_*.png → Cropped head
"""

add({
    "id": 21, "type": "Note",
    "pos": [-600, 800], "size": [550, 500],
    "properties": {},
    "widgets_values": [NOTE_TEXT],
    "title": "Instructions"
})

# T-pose skeleton creation note
SKELETON_NOTE = """CREATE YOUR T-POSE SKELETON:

Option 1: Download a premade one
  - Search "OpenPose T-pose skeleton" 
  - Or use any mannequin/stick figure image

Option 2: Generate with OpenPose
  - Use ControlNet Preprocessor to extract pose from any T-pose image
  
Option 3: Draw a simple one
  - Black background, white stick figure
  - Arms horizontal at shoulder height
  - Legs slightly apart

The skeleton should be:
- 1024x1024 pixels
- Centered
- Arms perfectly horizontal (T-pose) or at 45° (A-pose)
- Clear contrast (black bg, white figure)
"""

add({
    "id": 22, "type": "Note",
    "pos": [-600, 1350], "size": [400, 350],
    "properties": {},
    "widgets_values": [SKELETON_NOTE],
    "title": "Creating T-Pose Skeleton"
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
        {"title": "Model Loading", "bounding": [-620, -240, 720, 280], "color": "#3f789e"},
        {"title": "ControlNet (Pose)", "bounding": [-620, 220, 720, 580], "color": "#8e3f5e"},
        {"title": "Prompt + Guidance", "bounding": [130, -130, 760, 500], "color": "#3f8e5e"},
        {"title": "Sampling", "bounding": [880, 220, 360, 700], "color": "#5e3f8e"},
        {"title": "Output", "bounding": [1930, 170, 860, 880], "color": "#8e6f3f"},
    ],
    "config": {},
    "extra": {},
    "version": 0.4,
}

out_path = __file__.replace("generate_reference_controlnet_workflow.py", "pii-chan_flux_tpose_controlnet.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"  {len(nodes)} nodes, {link_id} links")
print(f"  ControlNet strength: {CONTROLNET_STRENGTH}")
print(f"  Control mode: {CONTROL_MODE} (pose)")
