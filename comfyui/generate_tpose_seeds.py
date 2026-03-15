"""Generate a ComfyUI workflow that runs the T-pose ControlNet pipeline
10 times with different noise seeds.

All model/prompt/controlnet nodes are shared. Only the sampling tail
(RandomNoise → SamplerCustomAdvanced → VAEDecode → SaveImage × 2 + ImageCrop)
is duplicated per seed iteration.

Run:  python comfyui/generate_tpose_seeds.py
"""
import json
import random

NUM_ITERATIONS = 10
BASE_SEED = 100000
OUTPUT_FILE = "comfyui/mira_flux_tpose_controlnet.json"

# Generate 10 distinct seeds
random.seed(42)  # reproducible
SEEDS = [random.randint(0, 2**53) for _ in range(NUM_ITERATIONS)]


def build_workflow():
    nodes = []
    links = []
    link_id = [0]  # mutable counter

    def next_link():
        link_id[0] += 1
        return link_id[0]

    # ── Shared nodes (IDs 1-15, matching original) ──────────────────────

    # 1: UNETLoader
    nodes.append({
        "id": 1, "type": "UNETLoader",
        "pos": [-600, -200], "size": [315, 82],
        "properties": {"Node name for S&R": "UNETLoader"},
        "widgets_values": ["flux_dev.safetensors", "default"],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
        "title": "Flux UNET"
    })

    # 2: DualCLIPLoader
    nodes.append({
        "id": 2, "type": "DualCLIPLoader",
        "pos": [-600, -70], "size": [315, 130],
        "properties": {"Node name for S&R": "DualCLIPLoader"},
        "widgets_values": ["t5xxl_fp16.safetensors", "clip_l.safetensors", "flux", "default"],
        "outputs": [{"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 0}],
        "title": "Dual CLIP"
    })

    # 3: VAELoader
    nodes.append({
        "id": 3, "type": "VAELoader",
        "pos": [-600, 120], "size": [315, 58],
        "properties": {"Node name for S&R": "VAELoader"},
        "widgets_values": ["ae.safetensors"],
        "outputs": [{"name": "VAE", "type": "VAE", "links": [], "slot_index": 0}],
        "title": "Flux VAE"
    })

    # 4: LoraLoader
    lk_unet_lora = next_link()
    lk_clip_lora = next_link()
    nodes.append({
        "id": 4, "type": "LoraLoader",
        "pos": [-220, -200], "size": [315, 126],
        "properties": {"Node name for S&R": "LoraLoader"},
        "widgets_values": ["RM_Anime_Cyberpunk_v0.5M.safetensors", 1, 1],
        "inputs": [
            {"name": "model", "type": "MODEL", "link": lk_unet_lora},
            {"name": "clip", "type": "CLIP", "link": lk_clip_lora},
        ],
        "outputs": [
            {"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0},
            {"name": "CLIP", "type": "CLIP", "links": [], "slot_index": 1},
        ],
        "title": "LoRA (style)"
    })
    links.append([lk_unet_lora, 1, 0, 4, 0, "MODEL"])
    links.append([lk_clip_lora, 2, 0, 4, 1, "CLIP"])
    nodes[0]["outputs"][0]["links"].append(lk_unet_lora)
    nodes[1]["outputs"][0]["links"].append(lk_clip_lora)

    # 5: ControlNetLoader
    nodes.append({
        "id": 5, "type": "ControlNetLoader",
        "pos": [-600, 250], "size": [315, 58],
        "properties": {"Node name for S&R": "ControlNetLoader"},
        "widgets_values": ["flux-controlnet-union.safetensors"],
        "outputs": [{"name": "CONTROL_NET", "type": "CONTROL_NET", "links": [], "slot_index": 0}],
        "title": "ControlNet Union (InstantX)"
    })

    # 6: LoadImage (skeleton)
    nodes.append({
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

    # 7: ControlNetApplyAdvanced
    lk_cn_model = next_link()
    lk_cn_image = next_link()
    nodes.append({
        "id": 7, "type": "ControlNetApplyAdvanced",
        "pos": [150, 250], "size": [320, 180],
        "properties": {"Node name for S&R": "ControlNetApplyAdvanced"},
        "widgets_values": [0.7, 0.0, 1.0],
        "inputs": [
            {"name": "positive", "type": "CONDITIONING", "link": None},  # filled below
            {"name": "negative", "type": "CONDITIONING", "link": None},
            {"name": "control_net", "type": "CONTROL_NET", "link": lk_cn_model},
            {"name": "image", "type": "IMAGE", "link": lk_cn_image},
        ],
        "outputs": [
            {"name": "positive", "type": "CONDITIONING", "links": [], "slot_index": 0},
            {"name": "negative", "type": "CONDITIONING", "links": [], "slot_index": 1},
        ],
        "title": "Apply ControlNet (strength=0.7)"
    })
    links.append([lk_cn_model, 5, 0, 7, 2, "CONTROL_NET"])
    links.append([lk_cn_image, 6, 0, 7, 3, "IMAGE"])
    nodes[4]["outputs"][0]["links"].append(lk_cn_model)   # ControlNetLoader
    nodes[5]["outputs"][0]["links"].append(lk_cn_image)    # LoadImage

    # 8: CLIPTextEncode
    lk_clip_to_prompt = next_link()
    lk_prompt_to_cn = next_link()
    nodes.append({
        "id": 8, "type": "CLIPTextEncode",
        "pos": [150, -100], "size": [450, 200],
        "properties": {"Node name for S&R": "CLIPTextEncode"},
        "widgets_values": [
            "anime, cyberpunk, cyborg, tight fitting exosuit, armor, 1girl, solo, \n"
            "looking straight at viewer, closed mouth, white hair, bob cut, face markings,\n"
            "robot, glowing eyes, futuristic, sci-fi, blush, short hair, dark purple eyes, purple glow,\n"
            "anime artwork retro cyberpunk anime art by Tsubasa Nakai, \n"
            "Painting, Hyperrealism, detailed, 80's inspired, synthwave, neon, vibrant, \n"
            "retro futurism, anime style, key visual, studio anime, highly detailed, \n"
            "big expressive eyes, black background, \n"
            "full body, front view, centered, symmetrical pose,\n"
            "even flat lighting, character reference sheet style"
        ],
        "inputs": [{"name": "clip", "type": "CLIP", "link": lk_clip_to_prompt}],
        "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [lk_prompt_to_cn], "slot_index": 0}],
        "title": "Positive Prompt (EDIT HERE)"
    })
    links.append([lk_clip_to_prompt, 4, 1, 8, 0, "CLIP"])
    links.append([lk_prompt_to_cn, 8, 0, 7, 0, "CONDITIONING"])
    nodes[3]["outputs"][1]["links"].append(lk_clip_to_prompt)  # LoRA CLIP out
    nodes[6]["inputs"][0]["link"] = lk_prompt_to_cn  # ControlNet positive in

    # 9: FluxGuidance
    lk_cn_to_guidance = next_link()
    nodes.append({
        "id": 9, "type": "FluxGuidance",
        "pos": [550, 250], "size": [280, 58],
        "properties": {"Node name for S&R": "FluxGuidance"},
        "widgets_values": [3.5],
        "inputs": [{"name": "conditioning", "type": "CONDITIONING", "link": lk_cn_to_guidance}],
        "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": [], "slot_index": 0}],
        "title": "Guidance (3.5)"
    })
    links.append([lk_cn_to_guidance, 7, 0, 9, 0, "CONDITIONING"])
    nodes[6]["outputs"][0]["links"].append(lk_cn_to_guidance)  # ControlNet positive out

    # 10: ModelSamplingFlux
    lk_lora_to_msf = next_link()
    nodes.append({
        "id": 10, "type": "ModelSamplingFlux",
        "pos": [150, 80], "size": [315, 130],
        "properties": {"Node name for S&R": "ModelSamplingFlux"},
        "widgets_values": [1.15, 0.5, 1024, 1024],
        "inputs": [{"name": "model", "type": "MODEL", "link": lk_lora_to_msf}],
        "outputs": [{"name": "MODEL", "type": "MODEL", "links": [], "slot_index": 0}],
        "title": "ModelSamplingFlux"
    })
    links.append([lk_lora_to_msf, 4, 0, 10, 0, "MODEL"])
    nodes[3]["outputs"][0]["links"].append(lk_lora_to_msf)  # LoRA MODEL out

    # Notes
    nodes.append({
        "id": 21, "type": "Note",
        "pos": [-600, 800], "size": [550, 300],
        "properties": {},
        "widgets_values": [
            "=== MIRA T-POSE SEED EXPLORATION ===\n\n"
            f"This workflow runs {NUM_ITERATIONS} iterations with different noise seeds.\n"
            "All share the same prompt, ControlNet, and model settings.\n\n"
            "Seeds: " + ", ".join(str(s) for s in SEEDS) + "\n\n"
            "Outputs:\n"
            "- mira_tpose_full_seedN_*.png → Full body\n"
            "- mira_tpose_head_seedN_*.png → Cropped head\n"
        ],
        "title": "Seed Exploration Info"
    })

    # ── Per-seed iteration nodes ────────────────────────────────────────
    # Each iteration gets its OWN copy of BasicGuider, KSamplerSelect,
    # BasicScheduler, and EmptySD3LatentImage to avoid ComfyUI cache reuse.
    #
    # Node ID scheme per iteration i (0-9):
    #   RandomNoise:          100 + i*10
    #   SamplerCustomAdvanced:100 + i*10 + 1
    #   VAEDecode:            100 + i*10 + 2
    #   SaveImage (full):     100 + i*10 + 3
    #   ImageCrop:            100 + i*10 + 4
    #   SaveImage (head):     100 + i*10 + 5
    #   BasicGuider:          100 + i*10 + 6
    #   KSamplerSelect:       100 + i*10 + 7
    #   BasicScheduler:       100 + i*10 + 8
    #   EmptySD3LatentImage:  100 + i*10 + 9

    for i, seed in enumerate(SEEDS):
        base_id = 100 + i * 10
        x_offset = 1300
        y_offset = i * 700

        # -- Per-iteration BasicGuider --
        guider_id = base_id + 6
        lk_msf_to_guider = next_link()
        lk_guid_to_guider = next_link()
        lk_guider_out = next_link()
        nodes.append({
            "id": guider_id, "type": "BasicGuider",
            "pos": [x_offset - 400, y_offset], "size": [222, 46],
            "properties": {"Node name for S&R": "BasicGuider"},
            "widgets_values": [],
            "inputs": [
                {"name": "model", "type": "MODEL", "link": lk_msf_to_guider},
                {"name": "conditioning", "type": "CONDITIONING", "link": lk_guid_to_guider},
            ],
            "outputs": [{"name": "GUIDER", "type": "GUIDER", "links": [lk_guider_out], "slot_index": 0}],
            "title": f"Guider (seed {i+1})"
        })
        links.append([lk_msf_to_guider, 10, 0, guider_id, 0, "MODEL"])
        links.append([lk_guid_to_guider, 9, 0, guider_id, 1, "CONDITIONING"])
        # Find ModelSamplingFlux (id=10) and FluxGuidance (id=9) by scanning nodes
        for n in nodes:
            if n["id"] == 10:
                n["outputs"][0]["links"].append(lk_msf_to_guider)
            if n["id"] == 9:
                n["outputs"][0]["links"].append(lk_guid_to_guider)

        # -- Per-iteration KSamplerSelect --
        sampler_id = base_id + 7
        lk_sampler_out = next_link()
        nodes.append({
            "id": sampler_id, "type": "KSamplerSelect",
            "pos": [x_offset - 400, y_offset + 100], "size": [315, 58],
            "properties": {"Node name for S&R": "KSamplerSelect"},
            "widgets_values": ["euler"],
            "outputs": [{"name": "SAMPLER", "type": "SAMPLER", "links": [lk_sampler_out], "slot_index": 0}],
            "title": f"Sampler Select (seed {i+1})"
        })

        # -- Per-iteration BasicScheduler --
        sched_id = base_id + 8
        lk_msf_to_sched = next_link()
        lk_sigmas_out = next_link()
        nodes.append({
            "id": sched_id, "type": "BasicScheduler",
            "pos": [x_offset - 400, y_offset + 200], "size": [315, 106],
            "properties": {"Node name for S&R": "BasicScheduler"},
            "widgets_values": ["simple", 30, 1],
            "inputs": [{"name": "model", "type": "MODEL", "link": lk_msf_to_sched}],
            "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "links": [lk_sigmas_out], "slot_index": 0}],
            "title": f"Scheduler (seed {i+1})"
        })
        links.append([lk_msf_to_sched, 10, 0, sched_id, 0, "MODEL"])
        for n in nodes:
            if n["id"] == 10:
                n["outputs"][0]["links"].append(lk_msf_to_sched)
                break

        # -- Per-iteration EmptySD3LatentImage --
        latent_id = base_id + 9
        lk_latent_out = next_link()
        nodes.append({
            "id": latent_id, "type": "EmptySD3LatentImage",
            "pos": [x_offset - 400, y_offset + 350], "size": [315, 106],
            "properties": {"Node name for S&R": "EmptySD3LatentImage"},
            "widgets_values": [1024, 1024, 1],
            "outputs": [{"name": "LATENT", "type": "LATENT", "links": [lk_latent_out], "slot_index": 0}],
            "title": f"Latent (seed {i+1})"
        })

        # RandomNoise
        lk_noise = next_link()
        nodes.append({
            "id": base_id, "type": "RandomNoise",
            "pos": [x_offset, y_offset], "size": [315, 82],
            "properties": {"Node name for S&R": "RandomNoise"},
            "widgets_values": [seed, "fixed"],
            "outputs": [{"name": "NOISE", "type": "NOISE", "links": [lk_noise], "slot_index": 0}],
            "title": f"Seed {i+1}: {seed}"
        })

        # SamplerCustomAdvanced
        lk_output = next_link()
        nodes.append({
            "id": base_id + 1, "type": "SamplerCustomAdvanced",
            "pos": [x_offset + 400, y_offset + 50], "size": [272, 180],
            "properties": {"Node name for S&R": "SamplerCustomAdvanced"},
            "widgets_values": [],
            "inputs": [
                {"name": "noise", "type": "NOISE", "link": lk_noise},
                {"name": "guider", "type": "GUIDER", "link": lk_guider_out},
                {"name": "sampler", "type": "SAMPLER", "link": lk_sampler_out},
                {"name": "sigmas", "type": "SIGMAS", "link": lk_sigmas_out},
                {"name": "latent_image", "type": "LATENT", "link": lk_latent_out},
            ],
            "outputs": [
                {"name": "output", "type": "LATENT", "links": [lk_output], "slot_index": 0},
                {"name": "denoised_output", "type": "LATENT", "links": [], "slot_index": 1},
            ],
            "title": f"Sampler (seed {i+1})"
        })
        links.append([lk_noise, base_id, 0, base_id + 1, 0, "NOISE"])

        # VAEDecode
        lk_vae_model = next_link()
        lk_img_full = next_link()
        lk_img_crop = next_link()

        nodes.append({
            "id": base_id + 2, "type": "VAEDecode",
            "pos": [x_offset + 750, y_offset + 80], "size": [210, 46],
            "properties": {"Node name for S&R": "VAEDecode"},
            "widgets_values": [],
            "inputs": [
                {"name": "samples", "type": "LATENT", "link": lk_output},
                {"name": "vae", "type": "VAE", "link": lk_vae_model},
            ],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [lk_img_full, lk_img_crop], "slot_index": 0}],
        })
        links.append([lk_output, base_id + 1, 0, base_id + 2, 0, "LATENT"])
        links.append([lk_vae_model, 3, 0, base_id + 2, 1, "VAE"])
        nodes[2]["outputs"][0]["links"].append(lk_vae_model)  # VAELoader

        # SaveImage (full)
        nodes.append({
            "id": base_id + 3, "type": "SaveImage",
            "pos": [x_offset + 1050, y_offset - 100], "size": [400, 400],
            "properties": {"Node name for S&R": "SaveImage"},
            "widgets_values": [f"mira_tpose_full_seed{i+1}"],
            "inputs": [{"name": "images", "type": "IMAGE", "link": lk_img_full}],
            "title": f"Save Full (seed {i+1})"
        })
        links.append([lk_img_full, base_id + 2, 0, base_id + 3, 0, "IMAGE"])

        # ImageCrop (head)
        lk_cropped = next_link()
        nodes.append({
            "id": base_id + 4, "type": "ImageCrop",
            "pos": [x_offset + 1050, y_offset + 350], "size": [315, 130],
            "properties": {"Node name for S&R": "ImageCrop"},
            "widgets_values": [512, 512, 256, 0],
            "inputs": [{"name": "image", "type": "IMAGE", "link": lk_img_crop}],
            "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [lk_cropped], "slot_index": 0}],
            "title": f"Crop Head (seed {i+1})"
        })
        links.append([lk_img_crop, base_id + 2, 0, base_id + 4, 0, "IMAGE"])

        # SaveImage (head)
        nodes.append({
            "id": base_id + 5, "type": "SaveImage",
            "pos": [x_offset + 1450, y_offset + 250], "size": [400, 400],
            "properties": {"Node name for S&R": "SaveImage"},
            "widgets_values": [f"mira_tpose_head_seed{i+1}"],
            "inputs": [{"name": "images", "type": "IMAGE", "link": lk_cropped}],
            "title": f"Save Head (seed {i+1})"
        })
        links.append([lk_cropped, base_id + 4, 0, base_id + 5, 0, "IMAGE"])

    # ── Build workflow ──────────────────────────────────────────────────
    workflow = {
        "last_node_id": max(n["id"] for n in nodes),
        "last_link_id": link_id[0],
        "nodes": nodes,
        "links": links,
        "groups": [
            {"title": "Model Loading", "bounding": [-620, -240, 720, 280], "color": "#3f789e"},
            {"title": "ControlNet (Pose)", "bounding": [-620, 220, 720, 580], "color": "#8e3f5e"},
            {"title": "Prompt + Guidance", "bounding": [130, -130, 760, 500], "color": "#3f8e5e"},
            {"title": "Shared Sampling Config", "bounding": [880, 220, 360, 700], "color": "#5e3f8e"},
            {"title": "Seed Iterations (10x)", "bounding": [1280, -120, 1600, 5100], "color": "#8e6f3f"},
        ],
        "config": {},
        "extra": {},
        "version": 0.4,
    }
    return workflow


if __name__ == "__main__":
    wf = build_workflow()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(wf, f, indent=2)
    n_nodes = len(wf["nodes"])
    n_links = len(wf["links"])
    print(f"Generated {OUTPUT_FILE}: {n_nodes} nodes, {n_links} links, {NUM_ITERATIONS} seeds")
    print(f"Seeds: {SEEDS}")
