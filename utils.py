import os
import sys
import json
import yt_dlp
from dotenv import load_dotenv
load_dotenv()  # Load variables from .env
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from moviepy import VideoFileClip
from yt_dlp.utils import download_range_func

def ensure_ffmpeg_in_path():
    """Prepends the local bin/ folder containing ffmpeg.exe to the system PATH."""
    project_dir = os.path.abspath(os.path.dirname(__file__))
    bin_dir = os.path.join(project_dir, "bin")
    
    # Check if we have local bin/ folder and prepend it to PATH
    if os.path.exists(bin_dir) and bin_dir not in os.environ["PATH"]:
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
        print(f"Added local bin directory to PATH: {bin_dir}")
    else:
        print("Local bin directory already in PATH or does not exist yet.")
        
    # Also check if imageio-ffmpeg has an executable and prepend its directory
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        if ffmpeg_dir not in os.environ["PATH"]:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
            print(f"Added imageio-ffmpeg directory to PATH: {ffmpeg_dir}")
    except ImportError:
        print("imageio-ffmpeg is not installed yet.")

class ViralClip(BaseModel):
    id: str = Field(description="Unique identifier for the clip, e.g. 'clip_1', 'clip_2', 'clip_3'.")
    suggested_title: str = Field(description="A short, punchy 3-6 word clickbaity title for this clip (to be burnt onto the video).")
    rationale: str = Field(description="Explain why this segment is highly engaging and has high viral potential.")
    title: str = Field(description="Duplicate of suggested_title for backwards compatibility.")
    reasoning: str = Field(description="Duplicate of rationale for backwards compatibility.")
    transcript_segment: str = Field(description="The transcript text for this 30-55 second segment.")
    start_time: str = Field(description="Start timestamp in MM:SS format.")
    end_time: str = Field(description="End timestamp in MM:SS format.")
    start_seconds: float = Field(description="Start time in seconds as a float.")
    end_seconds: float = Field(description="End time in seconds as a float.")
    virality_score: int = Field(description="Predicted virality score from 1 to 100 based on hook and retention.")

class ViralClipsList(BaseModel):
    clips: list[ViralClip] = Field(description="List of the top 3 viral clips identified from the video.")

def get_video_info(url):
    """Fetches YouTube video metadata without downloading it."""
    ensure_ffmpeg_in_path()
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),  # in seconds
            'thumbnail': info.get('thumbnail'),
            'id': info.get('id'),
            'webpage_url': info.get('webpage_url')
        }

def extract_youtube_id(url):
    """Extracts the 11-character YouTube video ID using regex or fallback."""
    import re
    # Specific regexes matching YouTube video structures and rejecting domain URLs
    patterns = [
        r'(?:v=|vi/|/vi/|youtu\.be/|/v/|/e/|/embed/|/shorts/|watch\?v=|&v=)([0-9A-Za-z_-]{11})',
        r'^[0-9A-Za-z_-]{11}$'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            candidate = match.group(1)
            # Rejects common domain pieces just in case
            if candidate not in ["www.youtube", "youtube.com", "youtu.be", "watch?v="]:
                return candidate
            
    # Fallback to get_video_info if regex doesn't match
    try:
        info = get_video_info(url)
        if info and info.get('id'):
            return info['id']
    except:
        pass
        
    import uuid
    return f"rand_{uuid.uuid4().hex[:7]}"

def download_audio(url, output_dir):
    """Downloads YouTube video audio as an M4A file with a unique Video ID and UUID transaction ID."""
    ensure_ffmpeg_in_path()
    
    video_id = extract_youtube_id(url)
    import uuid
    transaction_id = f"{video_id}_{uuid.uuid4().hex[:8]}"
    
    # Clean output path template with unique transaction_id
    outtmpl = os.path.join(output_dir, f'audio_{transaction_id}.%(ext)s')
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        print(f"Downloading audio track for video ID {video_id} with transaction {transaction_id}...")
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        
        # In case the extension resolved differently (e.g. webm)
        base, _ = os.path.splitext(filename)
        for ext in ['.m4a', '.webm', '.ogg', '.wav', '.mp3']:
            test_path = base + ext
            if os.path.exists(test_path):
                print(f"Downloaded audio to: {test_path}")
                return test_path
                
        if os.path.exists(filename):
            print(f"Downloaded audio to: {filename}")
            return filename
            
        raise FileNotFoundError("Could not locate the downloaded audio file.")

def find_viral_clip(audio_path, api_key, num_clips=3, model='gemini-2.5-flash'):
    """Uploads audio file to Gemini, asks it to identify the top N most viral 30-55s clips."""
    client = genai.Client(api_key=api_key)
    
    print(f"Uploading audio file '{audio_path}' to Gemini File API...")
    audio_file = client.files.upload(file=audio_path)
    print(f"Audio file uploaded successfully: {audio_file.name}")
    
    prompt = (
        "You are an expert social media strategist and viral video editor. "
        f"Listen to this audio track and identify the top {num_clips} most engaging, viral segments "
        "(each contiguous and strictly between 30 to 55 seconds in duration) "
        "that would make highly engaging, viral YouTube Shorts, TikToks, or Instagram Reels. "
        "Look for a strong hook at the start of each segment and a compelling narrative or high-retention content. "
        "Each clip in the returned list must strictly contain: "
        "- id: a unique identifier (e.g., 'clip_1', 'clip_2', 'clip_3') "
        "- suggested_title: a short, punchy 3-6 word clickbaity title for this clip "
        "- rationale: explain why this segment has high virality potential "
        "- title: same as suggested_title "
        "- reasoning: same as rationale "
        "- start_time: start timestamp in MM:SS format "
        "- end_time: end timestamp in MM:SS format "
        "- start_seconds: start time in seconds as a float "
        "- end_seconds: end time in seconds as a float "
        "- virality_score: predicted virality score from 1 to 100. "
        "Return your response strictly in the requested JSON format containing a list of these clips."
    )
    
    try:
        print(f"Sending audio and prompt to Gemini Model '{model}'...")
        response = client.models.generate_content(
            model=model,
            contents=[audio_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ViralClipsList,
                temperature=0.2
            )
        )
        result_json = response.text
        print("Received response from Gemini API.")
    finally:
        # Clean up the file from Gemini storage
        try:
            print("Cleaning up file from Gemini cloud storage...")
            client.files.delete(name=audio_file.name)
            print("Successfully deleted audio file from Gemini cloud.")
        except Exception as e:
            print(f"Warning: Failed to delete Gemini file: {e}")
            
    # Parse and return JSON
    return json.loads(result_json)

def download_video_range(url, start_secs, end_secs, output_path):
    """Downloads only the specified segment of the video in high quality."""
    ensure_ffmpeg_in_path()
    
    ydl_opts = {
        'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
        'merge_output_format': 'mp4',
        'outtmpl': output_path,
        'download_ranges': download_range_func(None, [(start_secs, end_secs)]),
        'force_keyframes_at_cuts': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    print(f"Downloading video segment from {start_secs}s to {end_secs}s...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    print(f"Segment downloaded to: {output_path}")
    return output_path

def crop_to_vertical(input_path, output_path):
    """Crops a horizontal video to a 9:16 vertical video layout with face tracking auto-reframe."""
    import cv2
    import numpy as np

    print(f"Starting auto-reframe & crop for video: '{input_path}'...")
    clip = VideoFileClip(input_path)
    w, h = clip.size
    
    target_ratio = 9 / 16
    current_ratio = w / h
    
    if current_ratio > target_ratio:
        # Horizontal video - scan for faces to center the crop dynamically
        print("Scanning video frames for face tracking auto-reframe...")
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        cap = cv2.VideoCapture(input_path)
        
        face_x_centers = []
        frame_count = 0
        sample_rate = 30  # Sample every 30th frame (approx. once per second) to keep processing fast
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % sample_rate == 0:
                # Resize to 50% for faster face detection processing
                small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30))
                
                if len(faces) > 0:
                    # Select largest face by bounding box area
                    largest_face = max(faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw, fh = largest_face
                    # Scale back coordinate center to original dimensions
                    face_center_x = (fx + fw / 2) * 2
                    face_x_centers.append(face_center_x)
                    
            frame_count += 1
            
        cap.release()
        
        # Calculate target horizontal center point
        if face_x_centers:
            # Use median to avoid transient outlier detections
            target_x_center = int(np.median(face_x_centers))
            print(f"Face tracked successfully! Median face center: {target_x_center}px")
        else:
            target_x_center = w // 2
            print(f"No faces detected in video. Defaulting to center: {target_x_center}px")
            
        crop_w = int(h * target_ratio)
        if crop_w % 2 != 0:
            crop_w -= 1
        crop_h = h
        if crop_h % 2 != 0:
            crop_h -= 1
            
        # Calculate horizontal crop bounds centered around tracked face
        x1 = target_x_center - (crop_w // 2)
        
        # Keep crop box fully inside original video bounds
        if x1 < 0:
            x1 = 0
        elif x1 + crop_w > w:
            x1 = w - crop_w
            
        y1 = (h - crop_h) // 2
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        
        print(f"Reframe dimensions: x1={x1}, x2={x2}, y1={y1}, y2={y2}")
        cropped_clip = clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)
    else:
        # Already vertical or narrower - crop top and bottom if needed
        crop_w = w
        if crop_w % 2 != 0:
            crop_w -= 1
        crop_h = int(w / target_ratio)
        if crop_h % 2 != 0:
            crop_h -= 1
            
        x1 = (w - crop_w) // 2
        y1 = (h - crop_h) // 2
        x2 = x1 + crop_w
        y2 = y1 + crop_h
        cropped_clip = clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)
        
    print("Encoding and saving final cropped video...")
    output_base = os.path.splitext(os.path.basename(output_path))[0]
    temp_audio_file = os.path.join(os.path.dirname(output_path), f"temp-audio-crop-{output_base}.m4a")
    cropped_clip.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=temp_audio_file,
        remove_temp=True,
        logger=None
    )
    
    # Close resources
    clip.close()
    cropped_clip.close()
    print(f"Cropped video saved to: {output_path}")
    return output_path


def burn_title(video_path, title_text, output_path):
    """Burns a styled title hook onto a video using FFmpeg drawtext (file-based)."""
    ensure_ffmpeg_in_path()
    import subprocess
    
    # Save the title to a temporary text file in the working directory
    # Relative path requires zero backslash/colon escaping in FFmpeg
    video_base = os.path.splitext(os.path.basename(video_path))[0]
    temp_text_path = f"temp_title_{video_base}.txt"
    with open(temp_text_path, "w", encoding="utf-8") as f:
        f.write(title_text)
        
    # Path to font on Windows (Arial Bold)
    font_path = "C\\:/Windows/Fonts/arialbd.ttf"
    if not os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
        font_opt = "font='Arial':"
    else:
        font_opt = f"fontfile='{font_path}':"
        
    # FFmpeg drawtext reading from the text file + scaling to even dimensions for H.264 compliance
    vf_filter = (
        f"drawtext=textfile='{temp_text_path}':"
        f"{font_opt}"
        f"fontsize=36:"
        f"fontcolor=yellow:"
        f"borderw=4:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y=150,"
        f"scale='trunc(iw/2)*2':'trunc(ih/2)*2'"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf_filter,
        "-c:v", "libx264",  # Explicitly encode video using standard H.264
        "-preset", "superfast",
        "-pix_fmt", "yuv420p", # Force standard 8-bit YUV 4:2:0 pixel format for maximum compatibility
        "-c:a", "copy",     # Copy audio stream without re-encoding
        output_path
    ]
    
    try:
        print(f"Executing FFmpeg subtitle burning: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg drawtext failed: {result.stderr}")
    finally:
        # Clean up temp file
        if os.path.exists(temp_text_path):
            try:
                os.remove(temp_text_path)
            except Exception:
                pass
                
    print(f"Burned title overlay saved to: {output_path}")
    return output_path


def crop_and_burn_title(input_path, title_text, api_key, model, output_path):
    """Crops a horizontal video to 9:16 vertical and burns timed, styled captions in a single pass using Gemini & FFmpeg."""
    ensure_ffmpeg_in_path()
    import cv2
    import numpy as np
    import subprocess
    import uuid

    print(f"Starting combined crop & subtitles burn for: '{input_path}'...")
    input_base = os.path.splitext(os.path.basename(input_path))[0]
    
    # 1. Get video width and height using OpenCV (very fast)
    cap = cv2.VideoCapture(input_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # 2. Run face detection auto-reframe to locate face center x-coordinate
    print("Scanning video frames for face tracking auto-reframe...")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    face_x_centers = []
    frame_count = 0
    sample_rate = 30  # Sample every 30th frame (approx. once per second) to keep processing fast
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % sample_rate == 0:
            # Resize to 50% for faster face detection processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                largest_face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = largest_face
                # Scale back coordinate center to original dimensions
                face_center_x = (fx + fw / 2) * 2
                face_x_centers.append(face_center_x)
                
        frame_count += 1
        
    cap.release()
    
    # Calculate target horizontal center point
    if face_x_centers:
        target_x_center = int(np.median(face_x_centers))
        print(f"Tracked face center: {target_x_center}px")
    else:
        target_x_center = w // 2
        print(f"No face detected. Using center: {target_x_center}px")
        
    # Calculate crop dimensions (9:16 layout)
    target_ratio = 9 / 16
    crop_w = int(h * target_ratio)
    if crop_w % 2 != 0:
        crop_w -= 1
    crop_h = h
    if crop_h % 2 != 0:
        crop_h -= 1
        
    x1 = target_x_center - (crop_w // 2)
    if x1 < 0:
        x1 = 0
    elif x1 + crop_w > w:
        x1 = w - crop_w
        
    # 3. Extract audio stream for Gemini transcription (takes <0.5s)
    print("Extracting audio stream for transcription...")
    temp_dir = os.path.dirname(output_path)
    audio_path = os.path.join(temp_dir, f"temp_audio_{input_base}.m4a")
    
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "copy", audio_path
    ], capture_output=True)
    
    # 4. Transcribe and generate SRT timed subtitles with Gemini API
    print("Uploading audio to Gemini for timed captions...")
    from google import genai
    client = genai.Client(api_key=api_key)
    audio_file = client.files.upload(file=audio_path)
    print("Upload complete. Generating word-by-word subtitles...")

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
            model=model,
            contents=[audio_file, prompt]
        )
        srt_content = response.text.strip()
    finally:
        try:
            client.files.delete(name=audio_file.name)
        except:
            pass
        # Clean up temp audio file
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
                
    # Clean markdown wrapper blocks if any
    if srt_content.startswith("```"):
        lines = srt_content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        srt_content = "\n".join(lines).strip()
        
    # Write SRT to the temp directory using relative paths to bypass escaping bugs
    srt_path = os.path.join("temp", f"subs_{input_base}.srt").replace("\\", "/")
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
        
    # 5. Format path for FFmpeg subtitles filter: since srt_path is relative with no colons/spaces, no escaping is needed
    safe_srt_path = srt_path
    
    # ASS Subtitle styling: Fontname=Impact, yellow fill (&H00FFFF), black outline, Alignment=2 (centered), MarginV=280 (lower-middle)
    vf_filter = (
        f"crop={crop_w}:{crop_h}:{x1}:0,"
        f"subtitles='{safe_srt_path}':force_style='Fontname=Impact,Fontsize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2.5,Alignment=2,MarginV=280',"
        f"scale='trunc(iw/2)*2':'trunc(ih/2)*2'"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "superfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",  # Encode audio to standard aac for player compatibility
        output_path
    ]
    
    try:
        print(f"Executing combined FFmpeg crop and subtitle burn: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Combined FFmpeg process failed: {result.stderr}")
    finally:
        # Clean up temp SRT file
        if os.path.exists(srt_path):
            try:
                os.remove(srt_path)
            except:
                pass
        # Clean up temp audio file
        if os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except:
                pass
                
    print(f"Rendered vertical cropped video with captions: {output_path}")
    return output_path


