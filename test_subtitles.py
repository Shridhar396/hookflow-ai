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

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[audio_file, prompt]
        )
        srt_content = response.text.strip()
    finally:
        client.files.delete(name=audio_file.name)
        print("Cleaned up Gemini file.")

    # Strip markdown block formatting if Gemini wrapped it
    if srt_content.startswith("```"):
        lines = srt_content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        srt_content = "\n".join(lines).strip()

    # Save SRT to the test_output directory
    srt_path = os.path.join(output_dir, "subs.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    print(f"Generated SRT: {srt_path}")
    print(srt_content[:500] + "...")

    # Step 5: Burn subtitles using FFmpeg subtitles filter
    print("--- STEP 5: Burning styled captions with FFmpeg ---")
    
    # Escape path for FFmpeg subtitles filter on Windows:
    # 1. Convert backslashes to forward slashes
    # 2. Escape the drive letter colon (e.g. D: -> D\:)
    # 3. Escape spaces (e.g. " " -> "\ ")
    safe_srt_path = srt_path.replace("\\", "/").replace(":", "\\:").replace(" ", "\\ ")
    
    vf_filter = f"subtitles='{safe_srt_path}':force_style='Fontname=Impact,Fontsize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2.5,Alignment=2,MarginV=280'"

    cmd = [
        "ffmpeg", "-y",
        "-i", cropped_clip,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        final_clip
    ]

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    
    if result.returncode != 0:
        print(f"FFmpeg failed: {result.stderr}")
    else:
        print(f"Success! Output video created at: {final_clip}")

if __name__ == "__main__":
    test_pipeline()
