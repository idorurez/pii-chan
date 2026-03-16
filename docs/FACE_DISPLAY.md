# Face Display System

## Current Status

✅ **Implemented:**
- `src/face.py` — Expression controller with state management
- `src/face_server.py` — WebSocket (port 18793) + HTTP server (port 8080)
- `ui/index.html` — CSS placeholder face with all expressions working
- `ui/live2d_test.html` — Live2D Cubism 4 renderer (Hiyori model, 60fps on Pi 5)
- `ui/live2d_sample/` — Hiyori model assets (moc3, textures, physics, motions)
- Wired into `main.py` voice loop (thinking/speaking/listening states)
- ComfyUI workflow for generating consistent character sprites
- **Live2D rendering tested on Pi 5 — 60fps vsync-locked in kiosk mode**

⏳ **Waiting on:**
- Custom Mira Live2D model (currently using sample Hiyori)
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
mira_neutral.png
mira_happy.png
mira_sad.png
mira_surprised.png
mira_thinking.png
mira_sleepy.png
mira_talking.png   (or talking_1.png, talking_2.png, talking_3.png for animation)
mira_excited.png
mira_confused.png
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

### Live2D Test (recommended)

```bash
cd ~/mira

# Start the face server (serves ui/ on port 8080, WebSocket on 18793)
./venv/bin/python -m src.face_server

# Launch Chromium in kiosk mode (fullscreen, no taskbar/chrome)
DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 XDG_RUNTIME_DIR=/run/user/1000 \
  chromium --password-store=basic --no-first-run \
  --disable-session-crashed-bubble --kiosk \
  http://localhost:8080/live2d_test.html
```

**Controls (requires keyboard):**
- Press `d` to toggle expression controls
- Press `1-5` for expressions (neutral/happy/sad/surprised/angry)
- Mouse movement controls eye tracking + head tilt

### CSS Placeholder Test

```bash
cd ~/mira
./venv/bin/python -m src.face_server

# Open browser to http://localhost:8080
# Press 'd' for debug panel to manually test expressions
```

## Kiosk Mode Notes

- Binary is `chromium` (not `chromium-browser`) on Raspberry Pi OS
- Use `--password-store=basic` to bypass the keyring prompt
- Use `--kiosk` for true fullscreen (no taskbar, no address bar)
- Must set `WAYLAND_DISPLAY=wayland-0` and `XDG_RUNTIME_DIR=/run/user/1000` when launching from SSH
- Renders at 60fps vsync-locked on Pi 5 (VideoCore VII GPU)
- Kill with `pkill -9 chromium` from SSH since kiosk mode has no close button

## Next Steps

1. Replace Hiyori sample model with custom Mira Live2D model
2. Wire face server expressions into Live2D parameters (happy/sad/thinking/etc.)
3. Add talking mouth animation driven by TTS state
4. Set up auto-launch on boot (systemd service for face server + chromium kiosk)
5. Test on dedicated display (HyperPixel 4.0)

## Files

- `src/face.py` — Python expression controller
- `src/face_server.py` — WebSocket + HTTP server
- `ui/index.html` — Browser renderer (CSS placeholder)
- `ui/live2d_test.html` — Live2D Cubism 4 renderer (PixiJS + pixi-live2d-display)
- `ui/live2d_sample/` — Hiyori sample model (model3.json, moc3, textures, physics, motions)
- `ui/sprites/` — Empty folder for character sprites
- `comfyui/mira_expression_workflow.json` — IP-Adapter workflow
- `comfyui/README.md` — ComfyUI setup instructions

## Dependencies

- `websockets` — Python WebSocket server for face state broadcast
- CDN-loaded in `live2d_test.html`:
  - PixiJS 6.5.10
  - Live2D Cubism Core (Cubism 4)
  - pixi-live2d-display 0.4.0
