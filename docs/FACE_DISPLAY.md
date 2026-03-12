# Face Display System

## Current Status

✅ **Implemented:**
- `src/face.py` — Expression controller with state management
- `src/face_server.py` — WebSocket (port 18793) + HTTP server (port 8080)
- `ui/index.html` — CSS placeholder face with all expressions working
- Wired into `main.py` voice loop (thinking/speaking/listening states)
- ComfyUI workflow for generating consistent character sprites

⏳ **Waiting on:**
- Actual character sprites from ComfyUI
- Swap placeholder CSS shapes with real PNGs

## Architecture

```
Python (face.py)  →  WebSocket  →  Browser (index.html)
   FaceController      state JSON      CSS/JS renderer
```

**Why browser-based:**
- Hardware accelerated CSS on Pi (VideoCore VII GPU)
- Easy to iterate (reload browser)
- Hot-swappable art (just replace files)
- Same approach VTuber apps use

## Expressions

| Expression | When Used |
|------------|-----------|
| `neutral` | Default idle state |
| `happy` | Good news, greeting, success |
| `sad` | Apologizing, bad news |
| `surprised` | Wake word detected, unexpected info |
| `thinking` | Waiting for LLM response |
| `sleepy` | Long idle, night mode |
| `talking` | During TTS playback |
| `excited` | Very good news |
| `confused` | Didn't understand input |

## Sprite Requirements

**Format:** PNG with transparency
**Resolution:** 512x512 or 1024x1024
**Location:** `ui/sprites/`

**Files needed:**
```
pii-chan_neutral.png
pii-chan_happy.png
pii-chan_sad.png
pii-chan_surprised.png
pii-chan_thinking.png
pii-chan_sleepy.png
pii-chan_talking.png   (or talking_1.png, talking_2.png, talking_3.png for animation)
pii-chan_excited.png
pii-chan_confused.png
```

## Animation Strategy

**Expression transitions:** CSS crossfade (opacity transition)
```css
.expression { transition: opacity 0.2s ease; opacity: 0; }
.expression.active { opacity: 1; }
```

**Talking animation:** Sprite sheet with 3-4 mouth frames
```css
.mouth { animation: talk 0.2s steps(4) infinite; }
```

**Idle animations:** CSS scale/breathing (already implemented)

## How to Test

```bash
cd ~/pii-chan
source venv/bin/activate
pip install websockets  # if needed

# Test face server standalone (cycles through expressions)
python -m src.face_server

# Open browser to http://localhost:8080
# Press 'd' for debug panel to manually test expressions
```

## Next Steps

1. Generate sprites with ComfyUI (`comfyui/pii-chan_expression_workflow.json`)
2. Place PNGs in `ui/sprites/`
3. Update `ui/index.html` to use sprites instead of CSS shapes
4. Test crossfade transitions
5. Add talking sprite sheet animation
6. Test on Pi display

## Files

- `src/face.py` — Python expression controller
- `src/face_server.py` — WebSocket + HTTP server
- `ui/index.html` — Browser renderer (currently CSS placeholder)
- `ui/sprites/` — Empty folder for character sprites
- `comfyui/pii-chan_expression_workflow.json` — IP-Adapter workflow
- `comfyui/README.md` — ComfyUI setup instructions
