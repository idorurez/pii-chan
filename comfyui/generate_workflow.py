"""Generate the Flux IP-Adapter expression workflow JSON for ComfyUI.

Matches the reference workflow pipeline:
  UNETLoader → LoraLoader → ApplyIPAdapterFlux → ModelSamplingFlux
  → per expression: CLIPTextEncode → FluxGuidance → BasicGuider
  → SamplerCustomAdvanced → VAEDecode → SaveImage

Uses ComfyUI-IPAdapter-Flux extension (Shakker-Labs/InstantX).

Run:  python comfyui/generate_workflow.py
"""
import json

# Style prompt from the reference image — LoRA needs these keywords to activate properly.
STYLE_PROMPT = (
    "anime, cyberpunk, cyborg, tight fitting exosuit, armor, 1girl, solo, \n"
    "looking straight at viewer, closed mouth, white hair, bob cut, face markings,\n"
    "robot, glowing eyes, futuristic, sci-fi, blush, short hair, dark purple eyes, purple glow,\n"
    "anime artwork retro cyberpunk anime art by Tsubasa Nakai, \n"
    "Painting, Hyperrealism, detailed, 80's inspired, synthwave, neon, vibrant, \n"
    "retro futurism, anime style, key visual, studio anime, highly detailed, \n"
    "big expressive eyes, black background, \n"
    "front view, centered, face only, \n"
    "above the shoulder camera framing, positioned in the center of the frame, \n"
    "middle of the image, no hands or arms visible in frame, mostly head shot neck up"
)

# Expression-specific overrides appended to the style prompt.
EXPRESSIONS = [
    ("neutral",   "calm relaxed expression, gentle slight smile"),
    ("happy",     "very happy expression, big warm smile, eyes closed with joy, blushing"),
    ("sad",       "sad expression, small frown, eyes looking down, small tear"),
    ("surprised", "surprised expression, eyes wide open, mouth open in shock"),
    ("thinking",  "thoughtful expression, looking up and to the right, finger on chin"),
    ("sleepy",    "drowsy sleepy expression, eyes half-closed, yawning"),
    ("talking",   "mid-sentence expression, mouth open while speaking, animated"),
    ("excited",   "extremely excited expression, sparkling eyes, huge grin"),
    ("confused",  "confused expression, head tilted to the side, one eyebrow raised"),
]

# ── Layout ──────────────────────────────────────────────────────────
LOADER_X = -550
LORA_X   = -180
MID_X    = 200
SAMP_X   = 550
EXPR_X   = 950    # expression prompt column
GUID_X   = 1350   # FluxGuidance column
BASIC_X  = 1600   # BasicGuider column
ADV_X    = 1850   # SamplerCustomAdvanced column
DEC_X    = 2200   # VAEDecode column
SAVE_X   = 2450   # SaveImage column
ROW_H    = 250
ROW_Y0   = -200

# ── Builders ────────────────────────────────────────────────────────
nodes = []
links = []
link_id = 0
node_idx = {}  # node id → index in nodes list

def L():
    global link_id; link_id += 1; return link_id

def add(node):
    node_idx[node["id"]] = len(nodes)
    nodes.append(node)

def out_links(nid, slot=0):
    """Get the links list for a node output slot (for appending)."""
    return nodes[node_idx[nid]]["outputs"][slot]["links"]

# ════════════════════════════════════════════════════════════════════
# SHARED NODES — same as reference workflow
# ════════════════════════════════════════════════════════════════════

# 1: UNETLoader
add({"id": 1, "type": "UNETLoader",
     "pos": [LOADER_X, -200], "size": [315, 82],
     "properties": {"Node name for S&R": "UNETLoader"},
     "widgets_values": ["flux_dev.safetensors", "default"],
     "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
     "title": "Flux UNET"})

# 2: DualCLIPLoader (order matches reference: t5xxl first, clip_l second)
add({"id": 2, "type": "DualCLIPLoader",
     "pos": [LOADER_X, -70], "size": [315, 130],
     "properties": {"Node name for S&R": "DualCLIPLoader"},
     "widgets_values": ["t5xxl_fp16.safetensors", "clip_l.safetensors", "flux", "default"],
     "outputs": [{"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 0}],
     "title": "Dual CLIP (Flux)"})

# 3: VAELoader
add({"id": 3, "type": "VAELoader",
     "pos": [LOADER_X, 120], "size": [315, 58],
     "properties": {"Node name for S&R": "VAELoader"},
     "widgets_values": ["ae.safetensors"],
     "outputs": [{"name": "VAE", "type": "VAE", "links": [], "slot_index": 0}],
     "title": "Flux VAE"})

# 4: LoraLoader (RM_Anime_Cyberpunk — same as reference)
l_unet_lora = L(); l_clip_lora = L()
add({"id": 4, "type": "LoraLoader",
     "pos": [LORA_X, -200], "size": [315, 126],
     "properties": {"Node name for S&R": "LoraLoader"},
     "widgets_values": ["RM_Anime_Cyberpunk_v0.5M.safetensors", 1, 1],
     "inputs": [
         {"name": "model", "type": "MODEL", "link": l_unet_lora},
         {"name": "clip",  "type": "CLIP",  "link": l_clip_lora},
     ],
     "outputs": [
         {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
         {"name": "CLIP",  "type": "CLIP",  "links": [], "slot_index": 1},
     ],
     "title": "LoRA (character style)"})
links.append([l_unet_lora, 1, 0, 4, 0, "MODEL"])
links.append([l_clip_lora, 2, 0, 4, 1, "CLIP"])
out_links(1).append(l_unet_lora)
out_links(2).append(l_clip_lora)

# 13: LoraLoader (Expression LoRA — chains after cyberpunk LoRA)
l_model_lora2 = L(); l_clip_lora2 = L()
add({"id": 13, "type": "LoraLoader",
     "pos": [LORA_X, -50], "size": [315, 126],
     "properties": {"Node name for S&R": "LoraLoader"},
     "widgets_values": ["CHANGE_ME_expression_lora.safetensors", 1, 1],
     "inputs": [
         {"name": "model", "type": "MODEL", "link": l_model_lora2},
         {"name": "clip",  "type": "CLIP",  "link": l_clip_lora2},
     ],
     "outputs": [
         {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
         {"name": "CLIP",  "type": "CLIP",  "links": [], "slot_index": 1},
     ],
     "title": "LoRA (expressions)"})
links.append([l_model_lora2, 4, 0, 13, 0, "MODEL"])
links.append([l_clip_lora2, 4, 1, 13, 1, "CLIP"])
out_links(4, 0).append(l_model_lora2)
out_links(4, 1).append(l_clip_lora2)

# 5: IPAdapterFluxLoader
add({"id": 5, "type": "IPAdapterFluxLoader",
     "pos": [LORA_X, 0], "size": [315, 106],
     "properties": {},
     "widgets_values": ["ip-adapter.bin", "google/siglip-so400m-patch14-384", "cuda"],
     "outputs": [{"name": "ipadapterFlux", "type": "IPADAPTERFLUX", "links": [], "slot_index": 0}],
     "title": "Load IP-Adapter Flux"})

# 6: LoadImage (reference character)
add({"id": 6, "type": "LoadImage",
     "pos": [LORA_X, 160], "size": [315, 314],
     "properties": {},
     "widgets_values": ["mira_reference.png", "image"],
     "outputs": [
         {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
         {"name": "MASK",  "type": "MASK",  "links": [], "slot_index": 1},
     ],
     "title": "Reference Character Image"})

# 7: ApplyIPAdapterFlux (LoRA model + IP-Adapter + reference image → locked model)
l_model_ipa = L(); l_ipa_apply = L(); l_img_apply = L()
add({"id": 7, "type": "ApplyIPAdapterFlux",
     "pos": [MID_X, -100], "size": [280, 170],
     "properties": {},
     "widgets_values": [0.95, 0.0, 1.0],  # weight, start_percent, end_percent (high = strong character lock)
     "inputs": [
         {"name": "model",          "type": "MODEL",         "link": l_model_ipa},
         {"name": "ipadapter_flux", "type": "IPADAPTERFLUX", "link": l_ipa_apply},
         {"name": "image",          "type": "IMAGE",         "link": l_img_apply},
     ],
     "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
     "title": "Apply IP-Adapter (Character Lock)"})
links.append([l_model_ipa, 13, 0, 7, 0, "MODEL"])
links.append([l_ipa_apply, 5, 0, 7, 1, "IPADAPTERFLUX"])
links.append([l_img_apply, 6, 0, 7, 2, "IMAGE"])
out_links(13, 0).append(l_model_ipa)
out_links(5).append(l_ipa_apply)
out_links(6).append(l_img_apply)

# 8: ModelSamplingFlux (auto shift based on resolution — matches reference)
l_model_msf = L()
add({"id": 8, "type": "ModelSamplingFlux",
     "pos": [MID_X, 130], "size": [315, 130],
     "properties": {"Node name for S&R": "ModelSamplingFlux"},
     "widgets_values": [1.15, 0.5, 1024, 1024],  # max_shift, base_shift, width, height
     "inputs": [
         {"name": "model", "type": "MODEL", "link": l_model_msf},
     ],
     "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
     "title": "ModelSamplingFlux"})
links.append([l_model_msf, 7, 0, 8, 0, "MODEL"])
out_links(7).append(l_model_msf)

# 9: LoadImage for head mask (RIGHT-CLICK → Open in MaskEditor to paint)
# Paint WHITE over the head/face area, BLACK everywhere else
add({"id": 9, "type": "LoadImage",
     "pos": [MID_X, 350], "size": [315, 400],
     "properties": {},
     "widgets_values": ["mira_reference.png", "image"],
     "outputs": [
         {"name": "IMAGE", "type": "IMAGE", "links": [], "slot_index": 0},
         {"name": "MASK",  "type": "MASK",  "links": [], "slot_index": 1},
     ],
     "title": "HEAD MASK (right-click → Open in MaskEditor)"})

# 10: VAEEncode (shared — encode reference image for img2img)
l_ref_vae_img = L(); l_ref_vae_model = L()
l_lat_encoded = L()
add({"id": 10, "type": "VAEEncode",
     "pos": [SAMP_X, -100], "size": [210, 46],
     "properties": {"Node name for S&R": "VAEEncode"},
     "widgets_values": [],
     "inputs": [
         {"name": "pixels", "type": "IMAGE", "link": l_ref_vae_img},
         {"name": "vae",    "type": "VAE",   "link": l_ref_vae_model},
     ],
     "outputs": [{"name": "LATENT", "type": "LATENT", "links": [l_lat_encoded], "slot_index": 0}],
     "title": "Encode Reference (img2img)"})
links.append([l_ref_vae_img, 6, 0, 10, 0, "IMAGE"])
links.append([l_ref_vae_model, 3, 0, 10, 1, "VAE"])
out_links(6).append(l_ref_vae_img)
out_links(3).append(l_ref_vae_model)

# 11: SetLatentNoiseMask (shared — head mask applied to encoded reference)
l_mask_link = L()
l_masked_lat = L()
add({"id": 11, "type": "SetLatentNoiseMask",
     "pos": [SAMP_X, -30], "size": [280, 46],
     "properties": {"Node name for S&R": "SetLatentNoiseMask"},
     "widgets_values": [],
     "inputs": [
         {"name": "samples", "type": "LATENT", "link": l_lat_encoded},
         {"name": "mask",    "type": "MASK",   "link": l_mask_link},
     ],
     "outputs": [{"name": "LATENT", "type": "LATENT", "links": [], "slot_index": 0}],
     "title": "Head Mask (shared)"})
links.append([l_lat_encoded, 10, 0, 11, 0, "LATENT"])
links.append([l_mask_link, 9, 1, 11, 1, "MASK"])
out_links(9, 1).append(l_mask_link)

# 12: KSamplerSelect (shared)
add({"id": 12, "type": "KSamplerSelect",
     "pos": [SAMP_X, 40], "size": [315, 58],
     "properties": {"Node name for S&R": "KSamplerSelect"},
     "widgets_values": ["euler"],
     "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "links": [], "slot_index": 0}],
     "title": "Sampler (euler)"})

# 14: RandomNoise (shared — fixed seed for consistency)
add({"id": 14, "type": "RandomNoise",
     "pos": [SAMP_X, 110], "size": [315, 82],
     "properties": {"Node name for S&R": "RandomNoise"},
     "widgets_values": [42, "fixed"],
     "outputs": [{"name": "NOISE", "type": "NOISE", "links": [], "slot_index": 0}],
     "title": "Noise (seed 42)"})

# ════════════════════════════════════════════════════════════════════
# PER-EXPRESSION BRANCHES
# Each: CLIPTextEncode → FluxGuidance → BasicGuider
#        → SamplerCustomAdvanced → VAEDecode → SaveImage
# ════════════════════════════════════════════════════════════════════

ROW_H = 350  # more vertical space for extra nodes per expression

for i, (name, expr_desc) in enumerate(EXPRESSIONS):
    y = ROW_Y0 + i * ROW_H
    prompt_id  = 20 + i   # CLIPTextEncode
    guid_id    = 30 + i   # FluxGuidance
    guider_id  = 40 + i   # BasicGuider
    adv_id     = 50 + i   # SamplerCustomAdvanced
    decode_id  = 60 + i   # VAEDecode
    save_id    = 70 + i   # SaveImage
    # Per-expression: only BasicScheduler stays per-expression (needs per-expression model link)
    sched_id   = 120 + i  # BasicScheduler

    full_prompt = STYLE_PROMPT + ", " + expr_desc

    # -- Per-expression BasicScheduler --
    l_model_sched = L(); l_sigmas_out = L()
    add({"id": sched_id, "type": "BasicScheduler",
         "pos": [SAMP_X, y + 180], "size": [315, 106],
         "properties": {"Node name for S&R": "BasicScheduler"},
         "widgets_values": ["simple", 30, 0.55],
         "inputs": [{"name": "model", "type": "MODEL", "link": l_model_sched}],
         "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "links": [l_sigmas_out], "slot_index": 0}],
         "title": f"Scheduler ({name})"})
    links.append([l_model_sched, 8, 0, sched_id, 0, "MODEL"])
    out_links(8).append(l_model_sched)

    # Allocate links for this branch
    l_clip_prompt  = L()  # CLIP → CLIPTextEncode
    l_prompt_guid  = L()  # CLIPTextEncode → FluxGuidance
    l_guid_guider  = L()  # FluxGuidance → BasicGuider
    l_model_guider = L()  # ModelSamplingFlux → BasicGuider
    l_noise_adv    = L()  # shared RandomNoise → SamplerCustomAdvanced
    l_guider_adv   = L()  # BasicGuider → SamplerCustomAdvanced
    l_samp_adv     = L()  # shared KSamplerSelect → SamplerCustomAdvanced
    l_lat_adv      = L()  # shared Head Mask → SamplerCustomAdvanced
    l_adv_dec      = L()  # SamplerCustomAdvanced → VAEDecode
    l_vae_dec      = L()  # VAELoader → VAEDecode
    l_dec_save     = L()  # VAEDecode → SaveImage

    # -- CLIPTextEncode (positive prompt) --
    add({"id": prompt_id, "type": "CLIPTextEncode",
         "pos": [EXPR_X, y], "size": [350, 130],
         "properties": {"Node name for S&R": "CLIPTextEncode"},
         "widgets_values": [full_prompt],
         "inputs": [{"name": "clip", "type": "CLIP", "link": l_clip_prompt}],
         "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING",
                       "links": [l_prompt_guid], "slot_index": 0}],
         "title": f"{name.upper()}"})
    links.append([l_clip_prompt, 13, 1, prompt_id, 0, "CLIP"])  # Expression LoRA CLIP out
    out_links(13, 1).append(l_clip_prompt)

    # -- FluxGuidance (guidance=3.5, matches reference) --
    add({"id": guid_id, "type": "FluxGuidance",
         "pos": [GUID_X, y], "size": [280, 58],
         "properties": {"Node name for S&R": "FluxGuidance"},
         "widgets_values": [3.5],
         "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": l_prompt_guid}],
         "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING",
                       "links": [l_guid_guider], "slot_index": 0}],
         "title": f"Guidance ({name})"})
    links.append([l_prompt_guid, prompt_id, 0, guid_id, 0, "CONDITIONING"])

    # -- BasicGuider (model + conditioned prompt → guider) --
    add({"id": guider_id, "type": "BasicGuider",
         "pos": [GUID_X, y + 80], "size": [280, 46],
         "properties": {"Node name for S&R": "BasicGuider"},
         "widgets_values": [],
         "inputs": [
             {"name": "model",        "type": "MODEL",        "link": l_model_guider},
             {"name": "conditioning", "type": "CONDITIONING",  "link": l_guid_guider},
         ],
         "outputs": [{"name": "GUIDER", "type": "GUIDER",
                       "links": [l_guider_adv], "slot_index": 0}],
         "title": f"Guider ({name})"})
    links.append([l_guid_guider, guid_id, 0, guider_id, 1, "CONDITIONING"])
    links.append([l_model_guider, 8, 0, guider_id, 0, "MODEL"])
    out_links(8).append(l_model_guider)

    # -- SamplerCustomAdvanced --
    add({"id": adv_id, "type": "SamplerCustomAdvanced",
         "pos": [ADV_X, y], "size": [272, 180],
         "properties": {"Node name for S&R": "SamplerCustomAdvanced"},
         "widgets_values": [],
         "inputs": [
             {"name": "noise",        "type": "NOISE",   "link": l_noise_adv},
             {"name": "guider",       "type": "GUIDER",  "link": l_guider_adv},
             {"name": "sampler",      "type": "SAMPLER", "link": l_samp_adv},
             {"name": "sigmas",       "type": "SIGMAS",  "link": l_sigmas_out},
             {"name": "latent_image", "type": "LATENT",  "link": l_lat_adv},
         ],
         "outputs": [
             {"name": "output",           "type": "LATENT", "links": [l_adv_dec], "slot_index": 0},
             {"name": "denoised_output",  "type": "LATENT", "links": [],          "slot_index": 1},
         ],
         "title": f"Sample ({name})"})
    links.append([l_noise_adv,  14, 0, adv_id, 0, "NOISE"])
    links.append([l_guider_adv, guider_id, 0, adv_id, 1, "GUIDER"])
    links.append([l_samp_adv,   12, 0, adv_id, 2, "SAMPLER"])
    links.append([l_sigmas_out, sched_id, 0, adv_id, 3, "SIGMAS"])
    links.append([l_lat_adv,    11, 0, adv_id, 4, "LATENT"])
    out_links(14).append(l_noise_adv)    # RandomNoise
    out_links(12).append(l_samp_adv)     # KSamplerSelect
    out_links(11).append(l_lat_adv)      # SetLatentNoiseMask

    # -- VAEDecode --
    add({"id": decode_id, "type": "VAEDecode",
         "pos": [DEC_X, y + 30], "size": [210, 46],
         "properties": {"Node name for S&R": "VAEDecode"},
         "widgets_values": [],
         "inputs": [
             {"name": "samples", "type": "LATENT", "link": l_adv_dec},
             {"name": "vae",     "type": "VAE",    "link": l_vae_dec},
         ],
         "outputs": [{"name": "IMAGE", "type": "IMAGE",
                       "links": [l_dec_save], "slot_index": 0}]})
    links.append([l_adv_dec, adv_id, 0, decode_id, 0, "LATENT"])
    links.append([l_vae_dec, 3, 0, decode_id, 1, "VAE"])
    out_links(3).append(l_vae_dec)

    # -- SaveImage --
    add({"id": save_id, "type": "SaveImage",
         "pos": [SAVE_X, y], "size": [400, 350],
         "properties": {"Node name for S&R": "SaveImage"},
         "widgets_values": [f"mira_{name}"],
         "inputs": [{"name": "images", "type": "IMAGE", "link": l_dec_save}],
         "title": f"Save: {name}"})
    links.append([l_dec_save, decode_id, 0, save_id, 0, "IMAGE"])

# ════════════════════════════════════════════════════════════════════
# NOTE
# ════════════════════════════════════════════════════════════════════

NOTE_TEXT = """=== MIRA FLUX EXPRESSION BATCH WORKFLOW ===

Pipeline (matches reference workflow):
  UNETLoader -> LoraLoader -> ApplyIPAdapterFlux -> ModelSamplingFlux
  -> per expression: CLIPTextEncode -> FluxGuidance -> BasicGuider
  -> SamplerCustomAdvanced -> VAEDecode -> SaveImage

EXTENSION REQUIRED:
  ComfyUI-IPAdapter-Flux (Shakker-Labs)
  https://github.com/Shakker-Labs/ComfyUI-IPAdapter-Flux

MODELS (update filenames in nodes to match yours):
  Flux UNET:   flux_dev.safetensors
  CLIP:        t5xxl_fp16.safetensors + clip_l.safetensors
  VAE:         ae.safetensors
  LoRA:        RM_Anime_Cyberpunk_v0.5M.safetensors
  IP-Adapter:  ip-adapter.bin  (in models/ipadapter-flux/)
  SigLIP:      google/siglip-so400m-patch14-384  (auto-downloaded)

HOW TO USE:
  1. Upload reference mira image as 'mira_reference.png'
  2. On the HEAD MASK node: right-click image → Open in MaskEditor
     Paint WHITE over head/face, leave body BLACK → Save to node
  3. Update model filenames if yours differ
  4. Queue Prompt - all 9 expressions generate in one batch
  5. Outputs in ComfyUI/output/ as mira_<expression>_00001.png
  6. Copy PNGs to ui/sprites/

TUNING:
  - IP-Adapter weight: 0.95 (higher = more like reference, lower for more variation)
  - Denoise: 0.55 (img2img — lower = more reference preserved, higher = more expression change)
  - Seed 42 (fixed) for consistency across expressions
  - Guidance 3.5 (in FluxGuidance nodes)
  - 30 steps, euler sampler, simple scheduler
"""

add({"id": 80, "type": "Note",
     "pos": [LOADER_X, 550], "size": [800, 450],
     "properties": {},
     "widgets_values": [NOTE_TEXT],
     "title": "Instructions"})

# ════════════════════════════════════════════════════════════════════
# ASSEMBLE
# ════════════════════════════════════════════════════════════════════

workflow = {
    "last_node_id": max(n["id"] for n in nodes),
    "last_link_id": link_id,
    "nodes": nodes,
    "links": links,
    "groups": [
        {"title": "Model + LoRA", "bounding": [LOADER_X - 10, -240, 700, 420], "color": "#3f789e"},
        {"title": "IP-Adapter (Character Lock)", "bounding": [MID_X - 10, -130, 310, 340], "color": "#8e6f3f"},
        {"title": "Sampling Setup", "bounding": [SAMP_X - 10, -130, 340, 680], "color": "#5e3f8e"},
        {"title": "Expression Branches (x9)",
         "bounding": [EXPR_X - 10, ROW_Y0 - 30, SAVE_X - EXPR_X + 440,
                       len(EXPRESSIONS) * ROW_H + 80],
         "color": "#3f8e5e"},
    ],
    "config": {},
    "extra": {},
    "version": 0.4,
}

out_path = __file__.replace("generate_workflow.py", "mira_flux_expressions.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2, ensure_ascii=False)

print(f"Wrote {out_path}")
print(f"  {len(nodes)} nodes, {link_id} links, {len(EXPRESSIONS)} expressions")
