#!/usr/bin/env python3
"""
Generate animated video from Mira expression images using Google Veo API.

Usage:
    python scripts/generate_video.py --expression neutral --prompt "subtle idle breathing, occasional blink"
    python scripts/generate_video.py --expression thinking --prompt "looks up and to the right, thoughtful"
    
Requires:
    pip install google-genai

API Key: Set GEMINI_API_KEY env var or use ~/.openclaw/credentials/gemini-api-key.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Install google-genai: pip install google-genai")
    sys.exit(1)


def load_api_key():
    """Load API key from env or credentials file."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    
    cred_path = Path.home() / ".openclaw" / "credentials" / "gemini-api-key.json"
    if cred_path.exists():
        with open(cred_path) as f:
            return json.load(f)["apiKey"]
    
    raise ValueError("No API key found. Set GEMINI_API_KEY or create credentials file.")


def load_image(path: str) -> types.Image:
    """Load image and return as Image type for the API."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    
    ext = path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(ext, "image/png")
    
    with open(path, "rb") as f:
        data = f.read()
    
    return types.Image(image_bytes=data, mime_type=mime_type)


def generate_video(
    image_path: str,
    prompt: str,
    output_path: str = None,
    duration_seconds: int = 5,
    reference_image_path: str = None,
    model: str = "veo-2.0-generate-001",
):
    """
    Generate video from image using Veo.
    
    Args:
        image_path: Path to the source image to animate
        prompt: Animation description
        output_path: Where to save the video (default: same dir as image)
        duration_seconds: Video length
        reference_image_path: Optional style/character reference image
        model: Veo model name (veo-2.0-generate-001 or veo-3.0-generate-001)
    """
    api_key = load_api_key()
    client = genai.Client(api_key=api_key)
    
    # Load source image
    print(f"Loading image: {image_path}")
    source_image = load_image(image_path)
    
    # Build the prompt with strict framing requirements
    full_prompt = f"""Animate this anime character image into a seamless looping video.

Animation: {prompt}

CRITICAL REQUIREMENTS:
- Output resolution: 800x480 (widescreen)
- Maintain exact art style from source image
- FRAMING: Keep upper torso and head visible as shown - do NOT zoom or crop differently
- Do NOT zoom in or out - keep the same character scale
- Maintain exact character appearance, colors, details
- Subtle natural movement only - no dramatic motions
- {duration_seconds} second seamless loop-ready animation
- Black background, no changes to background
- Character should not drift or move position in frame
"""
    
    # Add reference context if provided
    if reference_image_path and Path(reference_image_path).exists():
        full_prompt += f"\nUse the full body A-pose reference for character consistency (arms, hands, body proportions)."
        print(f"Note: Reference image context added to prompt")
    
    print(f"Model: {model}")
    print(f"Generating video with prompt: {prompt[:60]}...")
    print("This may take 2-5 minutes...")
    
    # Start video generation
    try:
        operation = client.models.generate_videos(
            model=model,
            prompt=full_prompt,
            image=source_image,
        )
    except Exception as e:
        print(f"Error starting generation: {e}")
        if "429" in str(e) or "quota" in str(e).lower():
            print("\nRate limited. Wait and try again later.")
        return None
    
    print(f"Operation started: {operation.name}")
    
    # Poll for completion
    poll_count = 0
    max_polls = 30  # ~10 minutes max
    while not operation.done and poll_count < max_polls:
        poll_count += 1
        print(f"  Waiting... ({poll_count * 20}s elapsed)")
        time.sleep(20)
        try:
            operation = client.operations.get(operation)
        except Exception as e:
            print(f"  Error polling: {e}")
            continue
        
        if operation.error:
            print(f"Error: {operation.error}")
            return None
    
    if not operation.done:
        print("Timeout waiting for video generation")
        return None
    
    print("Generation complete!")
    
    # Determine output path
    if not output_path:
        img_path = Path(image_path)
        output_dir = img_path.parent.parent / "animations"
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"{img_path.stem}.mp4"
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(exist_ok=True)
    
    # Extract and save video
    result = operation.result
    if hasattr(result, 'generated_videos') and result.generated_videos:
        for i, gv in enumerate(result.generated_videos):
            video_data = None
            
            # Try different ways to get video bytes
            if hasattr(gv, 'video'):
                video = gv.video
                
                # Check for direct bytes
                if hasattr(video, 'video_bytes') and video.video_bytes:
                    video_data = video.video_bytes
                elif isinstance(video, bytes):
                    video_data = video
                
                # Check for URI (download required)
                elif hasattr(video, 'uri') and video.uri:
                    print(f"Downloading video from: {video.uri[:60]}...")
                    try:
                        import urllib.request
                        req = urllib.request.Request(video.uri)
                        req.add_header('x-goog-api-key', api_key)
                        with urllib.request.urlopen(req) as response:
                            video_data = response.read()
                        print(f"  Downloaded {len(video_data):,} bytes")
                    except Exception as e:
                        print(f"  Download failed: {e}")
                        # Try with httpx if available
                        try:
                            import httpx
                            resp = httpx.get(video.uri, headers={'x-goog-api-key': api_key})
                            video_data = resp.content
                            print(f"  Downloaded {len(video_data):,} bytes (httpx)")
                        except:
                            print(f"  Video URL (download manually): {video.uri}")
                            continue
            
            if video_data:
                save_path = output_path if i == 0 else output_path.with_stem(f"{output_path.stem}_{i}")
                with open(save_path, 'wb') as f:
                    f.write(video_data)
                print(f"[OK] Saved: {save_path} ({len(video_data):,} bytes)")
                return str(save_path)
    
    print(f"No video data found in result: {result}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate Mira animation videos")
    parser.add_argument("--expression", "-e", default="neutral",
                       help="Expression name (neutral, thinking, listening, talking)")
    parser.add_argument("--prompt", "-p", required=True,
                       help="Animation prompt describing the motion")
    parser.add_argument("--image", "-i",
                       help="Path to source image (default: avatar/mira/expressions/mira_{expression}.png)")
    parser.add_argument("--reference", "-r",
                       help="Path to A-pose reference image")
    parser.add_argument("--output", "-o",
                       help="Output video path (default: avatar/mira/animations/{expression}.mp4)")
    parser.add_argument("--duration", "-d", type=int, default=5,
                       help="Video duration in seconds")
    parser.add_argument("--model", "-m", default="veo-2.0-generate-001",
                       choices=["veo-2.0-generate-001", "veo-3.0-generate-001", "veo-3.0-fast-generate-001"],
                       help="Veo model to use")
    
    args = parser.parse_args()
    
    # Default image path
    if not args.image:
        args.image = f"avatar/mira/expressions/mira_{args.expression}.png"
    
    # Default reference (A-pose full body)
    if not args.reference:
        apose_paths = [
            "avatar/mira/apose_ref.png",
            "avatar/mira/a_pose_ref3.png",
            "avatar/mira/mira_tpose_full_00016_.png",
        ]
        for ref_path in apose_paths:
            if Path(ref_path).exists():
                args.reference = ref_path
                break
    
    generate_video(
        image_path=args.image,
        prompt=args.prompt,
        output_path=args.output,
        duration_seconds=args.duration,
        reference_image_path=args.reference,
        model=args.model,
    )


# Expression presets
PRESETS = {
    "neutral": "subtle idle breathing loop, occasional natural blink every 3-4 seconds, relaxed expression, minimal head movement, calm and peaceful, MOUTH CLOSED - no lip movement, lips stay still",
    "thinking": "character looks up and to the right, slight head tilt, thoughtful expression, eyes moving as if pondering, hold pose with subtle movement, mouth closed, no lip movement",
    "listening": "character tilts head slightly to the side, leans in subtly, attentive focused expression, alert eyes, slight anticipation, mouth closed, lips still",
    "talking": "character speaking naturally, mouth opening and closing in conversation rhythm, slight head movements, engaged expression, eyes active",
}


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Mira Animation Generator (Veo)")
        print("=" * 40)
        print("\nPreset prompts:")
        for name, prompt in PRESETS.items():
            print(f"\n  {name}:")
            print(f"    {prompt[:70]}...")
        print("\nUsage:")
        print("  python scripts/generate_video.py -e neutral -p 'subtle idle breathing, occasional blink'")
        print("\nFull example:")
        print(f"  python scripts/generate_video.py -e neutral -p \"{PRESETS['neutral']}\"")
        print()
    else:
        main()
