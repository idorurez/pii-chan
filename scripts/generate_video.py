#!/usr/bin/env python3
"""
Generate animated video from Mira expression images using Google Veo 2 API.

Usage:
    python scripts/generate_video.py --expression neutral --prompt "subtle idle breathing, occasional blink"
    python scripts/generate_video.py --expression thinking --prompt "looks up and to the right, thoughtful"
    
Requires:
    pip install google-generativeai

API Key: Set GEMINI_API_KEY env var or use ~/.openclaw/credentials/gemini-api-key.json
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

try:
    import google.generativeai as genai
except ImportError:
    print("Install google-generativeai: pip install google-generativeai")
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


def load_image_as_base64(path: str) -> tuple[str, str]:
    """Load image and return (base64_data, mime_type)."""
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
        data = base64.b64encode(f.read()).decode("utf-8")
    
    return data, mime_type


def generate_video(
    image_path: str,
    prompt: str,
    output_path: str = None,
    duration_seconds: int = 5,
    reference_image_path: str = None,
):
    """
    Generate video from image using Veo 2.
    
    Args:
        image_path: Path to the source image to animate
        prompt: Animation description
        output_path: Where to save the video (default: same name as image with .mp4)
        duration_seconds: Video length (3-8 seconds typically)
        reference_image_path: Optional style/character reference image
    """
    api_key = load_api_key()
    genai.configure(api_key=api_key)
    
    # Load source image
    print(f"Loading image: {image_path}")
    img_data, img_mime = load_image_as_base64(image_path)
    
    # Build the prompt with strict framing requirements
    full_prompt = f"""Animate this anime character image into a seamless looping video.

Animation: {prompt}

CRITICAL REQUIREMENTS:
- Output resolution: 800x480 (widescreen)
- Maintain exact art style from source images
- Use the A-pose full body image as character reference for style consistency
- FRAMING: Keep upper torso and head visible as shown in first image - expand canvas to 800x480 but maintain this framing
- Do NOT zoom in or out - keep the same character scale
- Maintain exact character appearance, colors, details
- Subtle natural movement only - no dramatic motions
- {duration_seconds} second seamless loop-ready animation
- Black background, no changes to background
- Character should not drift or move position in frame
"""
    
    # Prepare content parts
    parts = [
        {"text": full_prompt},
        {
            "inline_data": {
                "mime_type": img_mime,
                "data": img_data
            }
        }
    ]
    
    # Add reference image if provided (full body A-pose for character consistency)
    if reference_image_path:
        print(f"Loading full body reference: {reference_image_path}")
        ref_data, ref_mime = load_image_as_base64(reference_image_path)
        parts.insert(1, {"text": "Full body A-pose reference - use this to understand the complete character design including arms, hands, and body proportions. The animation should show the upper body framing from the first image, but use this reference for any visible arm/hand movements:"})
        parts.insert(2, {
            "inline_data": {
                "mime_type": ref_mime,
                "data": ref_data
            }
        })
    
    print(f"Generating video with prompt: {prompt[:80]}...")
    print("This may take 1-3 minutes...")
    
    # Use Veo 3 model for video generation
    # Model names to try: veo-3.0-generate-001, veo-2.0-generate-001
    model = genai.GenerativeModel("veo-3.0-generate-001")
    
    try:
        response = model.generate_content(
            parts,
            generation_config={
                "response_mime_type": "video/mp4",
            }
        )
        
        # Extract video data
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data.mime_type.startswith("video/"):
                    video_data = base64.b64decode(part.inline_data.data)
                    
                    # Determine output path
                    if not output_path:
                        output_path = Path(image_path).with_suffix(".mp4")
                    
                    with open(output_path, "wb") as f:
                        f.write(video_data)
                    
                    print(f"✓ Video saved: {output_path}")
                    return str(output_path)
        
        print("No video data in response")
        print(f"Response: {response}")
        return None
        
    except Exception as e:
        print(f"Error generating video: {e}")
        
        # Check if it's a model availability issue
        if "not found" in str(e).lower() or "not supported" in str(e).lower():
            print("\nVeo 2 may not be available via this API endpoint.")
            print("Try using AI Studio directly or check API documentation for current model names.")
        
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
                       help="Path to T-pose reference image")
    parser.add_argument("--output", "-o",
                       help="Output video path (default: same as input with .mp4)")
    parser.add_argument("--duration", "-d", type=int, default=5,
                       help="Video duration in seconds")
    
    args = parser.parse_args()
    
    # Default image path
    if not args.image:
        args.image = f"avatar/mira/expressions/mira_{args.expression}.png"
    
    # Default reference (A-pose full body)
    if not args.reference:
        # Prefer A-pose over T-pose for more natural reference
        apose_paths = [
            "avatar/mira/apose_ref.png",
            "avatar/mira/a_pose_ref3.png",
            "avatar/mira/mira_tpose_full_00016_.png",  # fallback
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
    )


# Expression presets
PRESETS = {
    "neutral": "subtle idle breathing loop, occasional natural blink every 3-4 seconds, relaxed expression, minimal head movement, calm and peaceful",
    "thinking": "character looks up and to the right, slight head tilt, thoughtful expression, eyes moving as if pondering, hold pose with subtle movement",
    "listening": "character tilts head slightly to the side, leans in subtly, attentive focused expression, alert eyes, slight anticipation",
    "talking": "character speaking naturally, mouth opening and closing in conversation rhythm, slight head movements, engaged expression, eyes active",
}


if __name__ == "__main__":
    # If no args, show presets
    if len(sys.argv) == 1:
        print("Mira Animation Generator")
        print("=" * 40)
        print("\nPreset prompts:")
        for name, prompt in PRESETS.items():
            print(f"\n  {name}:")
            print(f"    {prompt}")
        print("\nUsage:")
        print("  python scripts/generate_video.py -e neutral -p 'subtle idle breathing, occasional blink'")
        print("\nOr use a preset:")
        print("  python scripts/generate_video.py -e thinking -p \"$(python -c \"from generate_video import PRESETS; print(PRESETS['thinking'])\")\"\n")
    else:
        main()
