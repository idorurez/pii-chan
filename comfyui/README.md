# ComfyUI Workflows for Mira

## Workflows

### `mira_expression_workflow.json`

IP-Adapter based workflow for generating consistent character expressions.

## Requirements

### Models Needed

Download and place in your ComfyUI models folder:

**Checkpoint (pick one):**
- [Animagine XL 3.1](https://civitai.com/models/260267) → `models/checkpoints/`
- [Counterfeit V3.0](https://civitai.com/models/4468) → `models/checkpoints/`
- Any anime SDXL model

**IP-Adapter:**
- [IP-Adapter Plus Face SDXL](https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors) → `models/ipadapter/`

**CLIP Vision:**
- [CLIP-ViT-H-14](https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors) → `models/clip_vision/` (rename to `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`)

### Custom Nodes Needed

Install via ComfyUI Manager:
- **IPAdapter Plus** (cubiq)

## How to Use

### Step 1: Create Your Reference Character

Generate or create your ideal Mira design:
- Cute mascot/anime style
- Simple, clean design
- Front-facing, centered
- Save as `mira_reference.png`

### Step 2: Load Workflow

1. Open ComfyUI
2. Drag `mira_expression_workflow.json` onto the canvas
3. Load your reference image in the "Reference Character Image" node
4. Update model paths if needed

### Step 3: Generate Expressions

Edit the `[EXPRESSION: ...]` part in the positive prompt:

| Expression | Prompt Addition |
|------------|-----------------|
| neutral | `[EXPRESSION: calm expression, slight smile, looking at viewer]` |
| happy | `[EXPRESSION: happy, big smile, closed eyes, blush, sparkles]` |
| sad | `[EXPRESSION: sad expression, frown, downcast eyes, tears]` |
| surprised | `[EXPRESSION: surprised, wide eyes, open mouth, shocked]` |
| thinking | `[EXPRESSION: thinking, looking up, finger on chin, pondering]` |
| sleepy | `[EXPRESSION: sleepy, half-closed eyes, drowsy, tired, zzz]` |
| talking | `[EXPRESSION: talking, open mouth, speaking, mid-sentence]` |
| excited | `[EXPRESSION: very happy, excited, sparkle eyes, grin, jumping]` |
| confused | `[EXPRESSION: confused, head tilt, raised eyebrow, question mark]` |

### Step 4: Export for Mira

Rename outputs and place in `ui/sprites/`:

```
mira_neutral.png
mira_happy.png
mira_sad.png
mira_surprised.png
mira_thinking.png
mira_sleepy.png
mira_talking.png
mira_excited.png
mira_confused.png
```

## Tips

- **Consistency:** Keep IP-Adapter weight at 0.8-0.9
- **Same seed:** Use fixed seed for more consistency across expressions
- **Only change expression:** Keep the base prompt identical, only modify `[EXPRESSION: ...]`
- **Batch generation:** Queue multiple prompts with different expressions

## Troubleshooting

**Character looks different each time:**
- Increase IP-Adapter weight (try 0.95)
- Make sure reference image is high quality
- Use same seed across all generations

**Expression not showing:**
- Reduce IP-Adapter weight slightly (try 0.75)
- Make expression keywords more prominent in prompt
- Try adding expression keywords at the start of the prompt

**Face details wrong:**
- Use IP-Adapter Plus Face specifically
- Ensure CLIP Vision model is loaded correctly
