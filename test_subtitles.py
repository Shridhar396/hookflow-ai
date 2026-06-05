import os
import sys
import subprocess
from dotenv import load_dotenv
load_dotenv()

# Add workspace to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import utils

from google import genai

def test_pipeline():
    url = "https://www.youtube.com/shorts/m87JgCndKoA"
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_output"))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    raw_clip = os.path.join(output_dir, "raw_short.mp4")
    cropped_clip = os.path.join(output_dir, "cropped_short.mp4")
    audio_clip = os.path.join(output_dir, "audio_short.m4a")
    final_clip = os.path.join(output_dir, "final_short.mp4")

    # Step 1: Download range
    print("--- STEP 1: Downloading video range (0s to 12s) ---")
    utils.download_video_range(url, 0, 12, raw_clip)

    # Step 2: Auto-reframe crop
    print("--- STEP 2: Cropping to vertical with face reframe ---")
    utils.crop_to_vertical(raw_clip, cropped_clip)

    # Step 3: Extract audio for transcription
    print("--- STEP 3: Extracting audio stream ---")
    utils.ensure_ffmpeg_in_path()
    subprocess.run([
        "ffmpeg", "-y", "-i", cropped_clip, "-vn", "-acodec", "copy", audio_clip
    ], capture_output=True)

    # Step 4: Transcribe and generate SRT with Gemini
    print("--- STEP 4: Requesting timed word captions from Gemini ---")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in env.")
        return

    client = genai.Client(api_key=api_key)
    print(f"Uploading audio file: {audio_clip}")
    audio_file = client.files.upload(file=audio_clip)
    print("Upload complete. Analyzing with Gemini...")

    prompt = (
        "You are an expert podcast video editor. Listen to this audio clip, transcribe it, and generate a standard SRT subtitle file. "
        "To make the captions look extremely engaging like modern TikTok/Shorts captions, follow these rules: "
        "1. Every subtitle entry MUST contain strictly 1 to 3 words. "
        "2. The duration of each subtitle must be very short (e.g. 0.3s to 0.8s) matching the voice exactly. "
        "3. Every word must be in UPPERCASE. "
        "4. Do NOT group large blocks of text. Make the words flash rapidly on the screen. "
        "5. Output ONLY the raw, valid SRT subtitle content. No explanation, no markdown tags."
    )

    mock_srt_content = """1
00:00:00,109 --> 00:00:00,369
DON'T

2
00:00:00,369 --> 00:00:00,589
BE

3
00:00:00,589 --> 00:00:00,839
FAT

4
00:00:00,909 --> 00:00:01,179
BUT
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[audio_file, prompt]
        )
        srt_content = response.text.strip()
    except Exception as e:
        print(f"Warning: Gemini API call failed ({e}). Falling back to local mock subtitles for pipeline verification.")
        srt_content = mock_srt_content
    finally:
        try:
            client.files.delete(name=audio_file.name)
            print("Cleaned up Gemini file.")
        except:
            pass

    # Strip markdown block formatting if Gemini wrapped it
    if srt_content.startswith("```"):
        lines = srt_content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        srt_content = "\n".join(lines).strip()

    # Sanitize and format SRT content using utils
    srt_content = utils.fix_srt_content(srt_content)

    # Save SRT to the test_output directory
    srt_path = os.path.join(output_dir, "subs.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"Generated SRT: {srt_path}")
    print(srt_content[:500] + "...")

    # Step 5: Render unified vertical cropped video with captions using utils
    print("--- STEP 5: Rendering production vertical short with crop_and_burn_title ---")
    unified_final_clip = os.path.join(output_dir, "final_unified.mp4")
    try:
        utils.crop_and_burn_title(
            raw_clip,
            "PHOENIX VS KD: CLUTCH MOMENT",
            api_key,
            "gemini-2.5-flash",
            unified_final_clip,
            highlight_color="Multi-Color Cycle"
        )
        print(f"Success! Unified production video created at: {unified_final_clip}")
    except Exception as e:
        print(f"Unified rendering failed: {e}")

if __name__ == "__main__":
    test_pipeline()
