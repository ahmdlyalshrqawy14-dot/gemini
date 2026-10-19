# FILE: src/generator.py
# FINAL, CLEAN VERSION: Compatible with per-slide audio sync, dynamic slides, and GitHub Actions.

import os
import json
import time
import random
import requests
from io import BytesIO
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import subprocess
import asyncio
import edge_tts

# --- Configuration ---
ASSETS_PATH = Path("assets")
FONT_FILE = ASSETS_PATH / "fonts/arial.ttf"
BACKGROUND_MUSIC_PATH = ASSETS_PATH / "music/bg_music.mp3"
FALLBACK_THUMBNAIL_FONT = ImageFont.load_default()
YOUR_NAME = "Chaitanya"

TTS_MAX_ATTEMPTS = 5
TTS_BACKOFF_SECONDS = 5


def fetch_visual(query, output_path):
    """
    Fetches an image from Pixabay based on the query.
    If no key or no results, returns "FALLBACK" to indicate a procedural background is needed.
    """
    pixabay_api_key = os.getenv("PIXABAY_API_KEY")
    if not pixabay_api_key:
        print("⚠️ PIXABAY_API_KEY not found. Flagging for fallback visual.")
        return "FALLBACK"

    try:
        params = {
            "key": pixabay_api_key,
            "q": query,
            "image_type": "photo",
            "orientation": "horizontal",
            "per_page": 3,
            "safesearch": "true"
        }
        response = requests.get("https://pixabay.com/api/", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('hits') and len(data['hits']) > 0:
            # Pick a random result from the top hits to add variety
            hit = random.choice(data['hits'])
            image_url = hit.get('largeImageURL')

            if image_url:
                image_response = requests.get(image_url, timeout=15)
                image_response.raise_for_status()
                # Determine output path, it should be an image since Pixabay API is image-focused here
                actual_path = str(output_path).replace('.mp4', '.jpg')
                with open(actual_path, 'wb') as f:
                    f.write(image_response.content)
                print(f"🖼️ Successfully fetched visual for query: '{query}'")
                return actual_path

        print(f"⚠️ No Pixabay results for query '{query}'. Flagging for fallback visual.")
        return "FALLBACK"

    except Exception as e:
        print(f"❌ Error fetching Pixabay image for query '{query}': {e}. Flagging for fallback.")
        return "FALLBACK"


async def _generate_audio_async(text, output_path):
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_audio(text, output_path):
    """Converts text to speech using edge-tts."""
    print(f"🎤 Converting script to speech...")
    for attempt in range(1, TTS_MAX_ATTEMPTS + 1):
        try:
            asyncio.run(_generate_audio_async(text, output_path))
            print(f"✅ Speech generated successfully!")
            return Path(output_path)
        except Exception as e:
            if attempt == TTS_MAX_ATTEMPTS:
                print(f"❌ ERROR: Failed to generate speech after {TTS_MAX_ATTEMPTS} attempts: {e}")
                raise
            delay = TTS_BACKOFF_SECONDS * (2 ** (attempt - 1)) + random.uniform(0, 2)
            print(f"⚠️ TTS attempt {attempt}/{TTS_MAX_ATTEMPTS} failed ({e}). Retrying in {delay:.1f}s...")
            time.sleep(delay)


def generate_curriculum(previous_titles=None):
    """Generates the entire course curriculum using Gemini."""
    print("🤖 No content plan found. Generating a new curriculum from scratch...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        #Optional: Add prior lesson titles for continuation
        history = ""
        if previous_titles:
            formatted = "\n".join([f"{i+1}. {t}" for i, t in enumerate(previous_titles)])
            history = f"The following lessons have already been created:\n{formatted}\n\nPlease continue from where this series left off.\n"

        prompt = f"""
        You are an expert AI educator. Generate a curriculum for a YouTube series called 'AI for Developers by {YOUR_NAME}'.
        {history}
        The style must be: 'Assume the viewer is a beginner or non-technical person starting their journey into AI as a developer.
        Use simple real-world analogies, relatable examples, and then connect to technical concepts.'

        The curriculum must guide a developer from absolute beginner to advanced AI, covering foundations like Generative AI, LLMs, Vector Databases, and Agentic AI...
        ...then continue into deep AI topics like Reinforcement Learning, Transformers internals, multi-agent systems, tool use, LangGraph, AI architecture, and more.

        Respond with ONLY a valid JSON object. The object must contain a key "lessons" which is a list of 20 lesson objects.
        Each lesson object must have these keys: "chapter", "part", "title", "status" (defaulted to "pending"), and "youtube_id" (defaulted to null).
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        curriculum = json.loads(json_string)
        print("✅ New curriculum generated successfully!")
        return curriculum
    except Exception as e:
        print(f"❌ CRITICAL ERROR: Failed to generate curriculum. {e}")
        raise


def generate_script(topic):
    """Generates a fast-paced, curiosity-driven documentary script."""
    print(f"🤖 Generating script for topic: '{topic}'...")
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
        prompt = f"""
        You are an expert documentary scriptwriter creating a video about '{topic}'.
        Language: Strictly English.
        Style: Fast-paced, curiosity-driven documentary/video-essay (reminiscent of Vox / Magnates Media / Kurzgesagt).
        Structure:
        - Hook the viewer within the first 5 seconds (start with an intriguing question or startling premise, avoid textbook introductions).
        - Break the script into concise scenes (~3 to 6 seconds of narration each).

        Respond with ONLY a valid JSON object.
        The JSON MUST have a "scenes" key containing an array of scene objects.
        Each scene object MUST have:
        - "scene_id": Integer index (starting from 1).
        - "narration": Punchy script text for voiceover.
        - "visual_search_query": Targeted English keywords for image/video retrieval (e.g., "cyber security hacker abstract").
        - "screen_text": 2-4 key impact words to display as prominent kinetic text on screen.

        Do not include any extra text, only the raw JSON.
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        json_string = response.text.strip().replace("```json", "").replace("```", "")
        content = json.loads(json_string)
        print("✅ Script generated successfully.")
        return content
    except Exception as e:
        print(f"❌ ERROR: Failed to generate script: {e}")
        raise


# def generate_visuals(output_dir, video_type, slide_content=None, thumbnail_title=None, slide_number=0, total_slides=0):
#     """Generates a single professional, PPT-style slide or a thumbnail."""
#     output_dir.mkdir(exist_ok=True, parents=True)
#     is_thumbnail = thumbnail_title is not None

#     width, height = (1920, 1080) if video_type == 'long' else (1080, 1920)
#     title = thumbnail_title if is_thumbnail else slide_content.get("title", "")
#     bg_image = get_pexels_image(title, video_type)

#     if not bg_image:
#         bg_image = Image.new('RGBA', (width, height), color=(12, 17, 29))
#     bg_image = bg_image.resize((width, height)).filter(ImageFilter.GaussianBlur(5))
#     darken_layer = Image.new('RGBA', bg_image.size, (0, 0, 0, 150))
#     final_bg = Image.alpha_composite(bg_image, darken_layer).convert("RGB")
#     if is_thumbnail and video_type == 'long':
#         w, h = final_bg.size
#         if h > w:
#             print("⚠️ Detected vertical thumbnail for long video. Rotating and resizing to 1920x1080...")
#             final_bg = final_bg.transpose(Image.ROTATE_270).resize((1920, 1080))
#     draw = ImageDraw.Draw(final_bg)

#     try:
#         title_font = ImageFont.truetype(str(FONT_FILE), 80 if video_type == 'long' else 90)
#         content_font = ImageFont.truetype(str(FONT_FILE), 45 if video_type == 'long' else 55)
#         footer_font = ImageFont.truetype(str(FONT_FILE), 25 if video_type == 'long' else 35)
#     except IOError:
#         title_font = content_font = footer_font = FALLBACK_THUMBNAIL_FONT

#     if not is_thumbnail:
#         header_height = int(height * 0.18)
#         draw.rectangle([0, 0, width, header_height], fill=(25, 40, 65, 200))
#         title_bbox = draw.textbbox((0, 0), title, font=title_font)
#         title_x = (width - (title_bbox[2] - title_bbox[0])) / 2
#         title_y = (header_height - (title_bbox[3] - title_bbox[1])) / 2
#         draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255))
#     else:
#         title_bbox = draw.textbbox((0, 0), title, font=title_font)
#         title_x = (width - (title_bbox[2] - title_bbox[0])) / 2
#         title_y = (height - (title_bbox[3] - title_bbox[1])) / 2
#         draw.text((title_x, title_y), title, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill="black")

#     if not is_thumbnail:
#         content = slide_content.get("content", "")
#         is_special_slide = len(content.split()) < 10

#         words = content.split()
#         lines = []
#         current_line = ""
#         for word in words:
#             test_line = f"{current_line} {word}".strip()
#             if draw.textbbox((0, 0), test_line, font=content_font)[2] < width * 0.85:
#                 current_line = test_line
#             else:
#                 lines.append(current_line)
#                 current_line = word
#         lines.append(current_line)

#         line_height = content_font.getbbox("A")[3] + 15
#         total_text_height = len(lines) * line_height
#         y_text = (height - total_text_height) / 2 if is_special_slide else header_height + 100

#         for line in lines:
#             line_bbox = draw.textbbox((0, 0), line, font=content_font)
#             line_x = (width - (line_bbox[2] - line_bbox[0])) / 2
#             draw.text((line_x, y_text), line, font=content_font, fill=(230, 230, 230))
#             y_text += line_height

#         footer_height = int(height * 0.06)
#         draw.rectangle([0, height - footer_height, width, height], fill=(25, 40, 65, 200))
#         draw.text((40, height - footer_height + 12), f"AI for Developers by {YOUR_NAME}", font=footer_font, fill=(180, 180, 180))
#         if total_slides > 0:
#             slide_num_text = f"Slide {slide_number} of {total_slides}"
#             slide_num_bbox = draw.textbbox((0, 0), slide_num_text, font=footer_font)
#             draw.text((width - slide_num_bbox[2] - 40, height - footer_height + 12), slide_num_text, font=footer_font, fill=(180, 180, 180))
#     file_prefix = "thumbnail" if is_thumbnail else f"slide_{slide_number:02d}"
#     path = output_dir / f"{file_prefix}.png"
#     final_bg.save(path)
#     return str(path)

def create_scene_video(audio_path, visual_path, screen_text, output_path):
    """
    Creates a scene combining audio, visual (with Ken Burns if image, or procedural fallback),
    and kinetic subtitles.
    """
    print(f"🎬 Assembling scene -> {output_path}")

    # 1. Get audio duration
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True
        )
        duration = float(result.stdout.strip())
    except Exception as e:
        print(f"❌ Failed to get audio duration: {e}")
        duration = 5.0 # fallback

    duration += 0.5 # Add small pad

    # 2. Build FFmpeg command for the visual layer
    filters = []
    inputs = []

    if visual_path == "FALLBACK" or not os.path.exists(visual_path):
        # Procedural fallback: Dark animated gradient / noise
        inputs.extend(["-f", "lavfi", "-i", f"color=c=black:s=1920x1080:d={duration}"])
        filters.append(f"[0:v]noise=alls=10:allf=t+u[bg]")
        visual_stream = "[bg]"
    else:
        # We have an image (Pixabay photo)
        inputs.extend(["-loop", "1", "-i", visual_path])
        # Ken Burns effect: subtle zoom in and pan
        # Scale to 1920x1080 while zooming in 1.15x over time
        zoom_speed = 0.0015
        filters.append(f"[0:v]scale=3840:-1,zoompan=z='min(zoom+{zoom_speed},1.15)':d={int(duration*30)}:s=1920x1080[bg]")
        visual_stream = "[bg]"

    # 3. Add text overlay if present
    if screen_text:
        safe_text = screen_text.replace("'", "").replace(":", "").replace("\\", "")
        # Add a nice drop shadow/box for visibility
        font_path = str(FONT_FILE)
        # Fallback to standard font if ours doesn't exist
        if not os.path.exists(font_path):
            font_path = "Arial"

        text_filter = f"drawtext=fontfile='{font_path}':text='{safe_text}':fontcolor=white:fontsize=96:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.6:boxborderw=20:shadowcolor=black:shadowx=5:shadowy=5"
        filters.append(f"{visual_stream}{text_filter}[v_out]")
        final_v_stream = "[v_out]"
    else:
        filters.append(f"{visual_stream}copy[v_out]")
        final_v_stream = "[v_out]"

    # Combine inputs and audio
    inputs.extend(["-i", audio_path])

    filter_complex = ";".join(filters)

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", final_v_stream,
        "-map", "1:a", # The second input is the audio
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("✅ Scene created.")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg scene creation failed: {e}")
        raise


def assemble_final_video(scene_paths, output_path):
    """Concatenates all scenes and mixes in background music with audio ducking."""
    print(f"🎬 Assembling final video -> {output_path}")

    # 1. Create a concat demuxer file
    concat_file = "concat_list.txt"
    with open(concat_file, "w") as f:
        for path in scene_paths:
            f.write(f"file '{path}'\n")

    # 2. Build FFmpeg command for concatenation and ducking
    cmd = ["ffmpeg", "-y"]

    # Input 0: Concatenated video/audio
    cmd.extend(["-f", "concat", "-safe", "0", "-i", concat_file])

    # Input 1: Background Music (if exists)
    has_bgm = BACKGROUND_MUSIC_PATH.exists()
    if has_bgm:
        cmd.extend(["-stream_loop", "-1", "-i", str(BACKGROUND_MUSIC_PATH)])

        # Audio ducking filter
        # sidechaincompress: lowers BGM volume when narration (main audio) plays
        filter_complex = (
            "[1:a]volume=0.15[bgm];"  # Lower base volume of BGM
            "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[a_out]" # Simple mix for now, sidechaincompress is complex and prone to errors if channels don't match
        )

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a_out]",
            "-c:v", "copy", # We can copy the video stream to save time
            "-c:a", "aac", "-b:a", "192k",
            "-shortest"
        ])
    else:
        cmd.extend(["-c", "copy"]) # Just copy if no BGM

    cmd.append(output_path)

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("✅ Final video assembled successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg final assembly failed: {e}")
        raise
    finally:
        if os.path.exists(concat_file):
            os.remove(concat_file)
