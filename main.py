import os
import re
import sys
import json
import datetime
import time
import traceback
from pathlib import Path
from src.generator import (
    generate_curriculum,
    generate_script,
    generate_audio,
    fetch_visual,
    create_scene_video,
    assemble_final_video,
    YOUR_NAME
)
from src.uploader import upload_to_youtube

CONTENT_PLAN_FILE = Path("content_plan.json")
OUTPUT_DIR = Path("output")
LESSONS_PER_RUN = 1

def get_content_plan():
    if not CONTENT_PLAN_FILE.exists():
        print("📄 content_plan.json not found. Generating new plan...")
        new_plan = generate_curriculum()
        with open(CONTENT_PLAN_FILE, 'w') as f:
            json.dump(new_plan, f, indent=2)
        print(f"✅ New curriculum saved to {CONTENT_PLAN_FILE}")
        return new_plan
    else:
        try:
            with open(CONTENT_PLAN_FILE, 'r') as f:
                plan = json.load(f)
            if not plan.get("lessons") or not isinstance(plan["lessons"], list):
                raise ValueError("⚠️ Invalid or empty lesson plan detected.")
            return plan
        except Exception as e:
            print(f"❌ ERROR loading existing plan: {e}. Regenerating...")
            new_plan = generate_curriculum()
            with open(CONTENT_PLAN_FILE, 'w') as f:
                json.dump(new_plan, f, indent=2)
            return new_plan


def update_content_plan(plan):
    with open(CONTENT_PLAN_FILE, 'w') as f:
        json.dump(plan, f, indent=2)



def produce_documentary_video(topic):
    print(f"\n▶️ Starting documentary production for Topic: '{topic}'")
    safe_topic = re.sub(r'[^\w]', '_', str(topic))[:20].strip('_')
    unique_id = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{safe_topic}"

    script_data = generate_script(topic)
    scenes = script_data.get('scenes', [])
    if not scenes:
        raise ValueError("Script generation returned no scenes.")

    scene_video_paths = []

    print(f"🎬 Processing {len(scenes)} scenes...")
    for scene in scenes:
        scene_id = scene.get('scene_id')
        narration = scene.get('narration')
        query = scene.get('visual_search_query')
        screen_text = scene.get('screen_text', '')

        print(f"\n--- Scene {scene_id} ---")

        # 1. Audio
        audio_path = OUTPUT_DIR / f"scene_{scene_id}_{unique_id}.wav"
        generate_audio(narration, str(audio_path))

        # 2. Visual
        visual_path = OUTPUT_DIR / f"visual_{scene_id}_{unique_id}.mp4" # or .jpg
        actual_visual_path = fetch_visual(query, str(visual_path))

        # 3. Combine Audio + Visual + Text -> Scene Video
        scene_video_path = OUTPUT_DIR / f"scene_video_{scene_id}_{unique_id}.mp4"
        create_scene_video(str(audio_path), actual_visual_path, screen_text, str(scene_video_path))
        scene_video_paths.append(str(scene_video_path))

    # 4. Final Assembly
    final_video_path = OUTPUT_DIR / f"final_video_{unique_id}.mp4"
    assemble_final_video(scene_video_paths, str(final_video_path))

    print("\n📤 Uploading to YouTube...")
    title = f"The Truth About {topic}"
    desc = f"A deep dive into {topic}. #Documentary #Tech"
    tags = f"{topic}, Documentary, Tech"

    # Optional upload
    video_id = upload_to_youtube(str(final_video_path), title, desc, tags)
    return video_id


def main():
    print("🚀 Starting Autonomous AI Course Generator (Documentary Mode)")
    print(f"📁 Current working dir: {os.getcwd()}")
    print(f"📁 OUTPUT_DIR: {OUTPUT_DIR.resolve()}")

    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        print(f"📁 Created output folder: {OUTPUT_DIR.exists()}")

        custom_topic = os.getenv("TOPIC", "").strip()

        if custom_topic:
            print(f"🌟 TOPIC environment variable found: '{custom_topic}'. Running one-off documentary video.")
            try:
                produce_documentary_video(custom_topic)
            except Exception as e:
                print(f"❌ Failed producing documentary for topic '{custom_topic}': {e}")
                traceback.print_exc()
                sys.exit(1)
        else:
            print("📅 No TOPIC environment variable found. Falling back to content_plan.json.")
            plan = get_content_plan()
            pending = [(i, lesson) for i, lesson in enumerate(plan['lessons']) if lesson['status'] == 'pending']

            if not pending:
                print("🎉 All lessons produced! Generating new content plan to restart from scratch...")

                previous_titles = [lesson['title'] for lesson in plan['lessons']]
                new_plan = generate_curriculum(previous_titles=previous_titles)
                update_content_plan(new_plan)
                plan = new_plan
                pending = [(i, lesson) for i, lesson in enumerate(new_plan['lessons']) if lesson['status'] == 'pending']
                if not pending:
                    print("⚠️ Curriculum generated but no valid lessons found.")
                    return

            failed_lessons = []
            for lesson_index, lesson in pending[:LESSONS_PER_RUN]:
                try:
                    video_id = produce_documentary_video(lesson['title'])
                    if video_id:
                        for original_lesson in plan['lessons']:
                            if original_lesson['title'].strip().lower() == lesson['title'].strip().lower():
                                original_lesson['status'] = 'complete'
                                original_lesson['youtube_id'] = video_id
                                print(f"✅ Completed lesson: {lesson['title']}")
                                break
                        else:
                            print(f"⚠️ Could not find lesson in plan to mark as complete: {lesson['title']}")
                    else:
                        print(f"⚠️ Upload skipped or failed for: {lesson['title']}")
                        # Even if skipped, we can mark complete for now to progress
                        for original_lesson in plan['lessons']:
                            if original_lesson['title'].strip().lower() == lesson['title'].strip().lower():
                                original_lesson['status'] = 'complete'
                                original_lesson['youtube_id'] = None
                                break
                except Exception as e:
                    print(f"❌ Failed producing lesson: {lesson['title']}")
                    traceback.print_exc()
                    failed_lessons.append(lesson['title'])
                finally:
                    update_content_plan(plan)
                    print("📦 Content plan saved.")

            if failed_lessons:
                print(f"\n❌ PIPELINE FAILED — {len(failed_lessons)} lesson(s) did not complete:")
                for title in failed_lessons:
                    print(f"   - {title}")
                sys.exit(1)

    except Exception as e:
        print("❌ Critical error in main()")
        traceback.print_exc()
        sys.exit(1)

    try:
        for file in OUTPUT_DIR.glob("*.wav"):
            file.unlink()
        for file in OUTPUT_DIR.glob("scene_*.mp4"):
            file.unlink()
        for file in OUTPUT_DIR.glob("visual_*.mp4"):
            file.unlink()
        for file in OUTPUT_DIR.glob("visual_*.jpg"):
            file.unlink()
        print("🧹 Cleaned up intermediate files.")
    except Exception as e:
        print(f"⚠️ Could not clean up intermediate files: {e}")

if __name__ == "__main__":
    main()
