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

def find_viral_clip(url_or_path, api_key, num_clips=3, model='gemini-2.5-flash', temp_dir='temp'):
    """Finds top N most viral clips from a YouTube URL/ID or a pre-downloaded audio path.
    Attempts to fetch subtitles from YouTube Transcript API if a URL/ID is provided.
    Falls back to uploading audio to the Gemini File API if transcripts are unavailable or if a path is passed.
    """
    import os
    import json
    
    transcript_text = None
    is_url = False
    
    # Check if url_or_path is a URL or YouTube ID
    if url_or_path.startswith("http://") or url_or_path.startswith("https://") or len(url_or_path) == 11:
        is_url = True
        video_id = extract_youtube_id(url_or_path)
        
        # Try fetching YouTube transcript
        try:
            print(f"Attempting to fetch YouTube transcript for video ID: {video_id}...")
            from youtube_transcript_api import YouTubeTranscriptApi
            api = YouTubeTranscriptApi()
            transcript = api.fetch(video_id)
            
            formatted_transcript = []
            for entry in transcript:
                start_time = entry.start
                mins = int(start_time // 60)
                secs = int(start_time % 60)
                formatted_transcript.append(f"[{mins:02d}:{secs:02d}] {entry.text}")
            transcript_text = "\n".join(formatted_transcript)
            print("Successfully retrieved YouTube transcript!")
        except Exception as transcript_err:
            print(f"Could not fetch YouTube transcript: {transcript_err}")
            print("Falling back to downloading audio and using Gemini File API...")

    client = genai.Client(api_key=api_key)
    
    if transcript_text:
        prompt = (
            "You are an expert social media strategist and viral video editor. "
            "Here is the transcript of a YouTube video with timestamps:\n\n"
            f"{transcript_text}\n\n"
            f"Analyze this transcript and identify the top {num_clips} most engaging, viral segments "
            "(each contiguous and strictly between 30 to 55 seconds in duration) "
            "that would make highly engaging, viral YouTube Shorts, TikToks, or Instagram Reels. "
            "Look for a strong hook at the start of each segment and a compelling narrative or high-retention content. "
            "Each clip in the returned list must strictly contain: "
            "- id: a unique identifier (e.g., 'clip_1', 'clip_2', 'clip_3') "
            "- suggested_title: a short, punchy 3-6 word clickbaity title for this clip "
            "- rationale: explain why this segment has high virality potential "
            "- title: same as suggested_title "
            "- reasoning: same as rationale "
            "- transcript_segment: the transcript text for this 30-55 second segment "
            "- start_time: start timestamp in MM:SS format "
            "- end_time: end timestamp in MM:SS format "
            "- start_seconds: start time in seconds as a float "
            "- end_seconds: end time in seconds as a float "
            "- virality_score: predicted virality score from 1 to 100. "
            "Return your response strictly in the requested JSON format containing a list of these clips."
        )
        
        print(f"Sending transcript to Gemini Model '{model}'...")
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ViralClipsList,
                temperature=0.2
            )
        )
        return json.loads(response.text)
        
    else:
        # We need to download audio if it was a URL, otherwise use the path provided
        audio_path = url_or_path
        downloaded = False
        if is_url:
            audio_path = download_audio(url_or_path, temp_dir)
            downloaded = True
            
        try:
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
                "- transcript_segment: the transcript text for this 30-55 second segment "
                "- start_time: start timestamp in MM:SS format "
                "- end_time: end timestamp in MM:SS format "
                "- start_seconds: start time in seconds as a float "
                "- end_seconds: end time in seconds as a float "
                "- virality_score: predicted virality score from 1 to 100. "
                "Return your response strictly in the requested JSON format containing a list of these clips."
            )
            
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
            return json.loads(result_json)
        finally:
            # Clean up the file from Gemini storage
            try:
                print("Cleaning up file from Gemini cloud storage...")
                client.files.delete(name=audio_file.name)
            except Exception as e:
                print(f"Warning: Failed to delete Gemini file: {e}")
            # Clean up local audio file if we downloaded it
            if downloaded and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except:
                    pass

def download_video_range(url, start_secs, end_secs, output_path):
    """Downloads only the specified segment of the video in high quality."""
    ensure_ffmpeg_in_path()
    
    ydl_opts = {
        'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
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
    import cv2
    import textwrap
    
    # 1. Spelling correction: Correct PHENIX/Phenix/phenix to PHOENIX/Phoenix/phoenix
    title_text = title_text.replace("PHENIX", "PHOENIX").replace("Phenix", "Phoenix").replace("phenix", "phoenix")
    
    # 2. Get video dimensions using OpenCV (very fast and reliable)
    cap = cv2.VideoCapture(video_path)
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    
    # 3. Wrap title text to fit within 9:16 vertical canvas (approx 28 characters max per line)
    lines = textwrap.wrap(title_text, width=28)
    wrapped_text = "\n".join(lines)
    max_line_len = max(len(l) for l in lines) if lines else 1
    
    # 4. Calculate dynamic font size based on video width and max line length
    # We want the text to span at most 85% of the video width
    calculated_font_size = int((video_width * 0.85) / (max_line_len * 0.6))
    # Keep font size within reasonable proportions: 4% to 7% of video width
    max_fs = int(video_width * 0.07)
    min_fs = int(video_width * 0.04)
    font_size = max(min(calculated_font_size, max_fs), min_fs)
    
    # 5. Shift title downward to clear mobile safe zones (placed at 12% of video height)
    y_position = int(video_height * 0.12)
    
    # Save the wrapped title to a temporary text file in the working directory
    # Relative path requires zero backslash/colon escaping in FFmpeg
    video_base = os.path.splitext(os.path.basename(video_path))[0]
    temp_text_path = f"temp_title_{video_base}.txt"
    with open(temp_text_path, "w", encoding="utf-8") as f:
        f.write(wrapped_text)
        
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
        f"fontsize={font_size}:"
        f"fontcolor=yellow:"
        f"borderw=4:"
        f"bordercolor=black:"
        f"x=(w-text_w)/2:"
        f"y={y_position},"
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


def clean_markdown_srt(srt_content):
    srt_content = srt_content.strip()
    
    # Let's find if there is a code block in the text
    import re
    code_block_match = re.search(r'```(?:srt)?\s*(.*?)\s*```', srt_content, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        srt_content = code_block_match.group(1).strip()
    else:
        # If there are no triple backticks but some single backticks or other text,
        # let's find the first occurrence of "1\n" or a timestamp to strip leading conversational text.
        # A standard SRT block starts with an integer or a timestamp.
        srt_match = re.search(r'(?:^|\n)(\d+\s*\n\d{2}:\d{2}:\d{2}.*)', srt_content, re.DOTALL)
        if srt_match:
            srt_content = srt_match.group(1).strip()
            
    return srt_content


def fix_srt_content(srt_text):
    import re
    
    def sanitize_time(t_str):
        t_str = t_str.strip().replace('.', ',')
        t_str = re.sub(r'[^0-9:,]', '', t_str)
        parts = t_str.split(':')
        
        try:
            if len(parts) == 3:
                if ',' in parts[-1]:
                    hh, mm, ss_mmm = parts[0], parts[1], parts[2]
                    ss, mmm = ss_mmm.split(',')
                    return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d},{int(mmm):03d}"
                else:
                    mm, ss, mmm = parts[0], parts[1], parts[2]
                    return f"00:{int(mm):02d}:{int(ss):02d},{int(mmm):03d}"
            elif len(parts) == 4:
                hh, mm, ss, mmm = parts[0], parts[1], parts[2], parts[3]
                return f"{int(hh):02d}:{int(mm):02d}:{int(ss):02d},{int(mmm):03d}"
            elif len(parts) == 2:
                if ',' in parts[-1]:
                    ss, mmm = parts[-1].split(',')
                    mm = parts[0]
                    return f"00:00:{int(ss):02d},{int(mmm):03d}"
                else:
                    mm, ss = parts[0], parts[1]
                    return f"00:{int(mm):02d}:{int(ss):02d},000"
            elif len(parts) == 1:
                val = float(parts[0].replace(',', '.'))
                hh = int(val // 3600)
                mm = int((val % 3600) // 60)
                ss = int(val % 60)
                mmm = int(round((val - int(val)) * 1000))
                return f"{hh:02d}:{mm:02d}:{ss:02d},{mmm:03d}"
        except Exception as e:
            print(f"Error sanitizing timestamp '{t_str}': {e}")
        return "00:00:00,000"

    lines = srt_text.splitlines()
    blocks = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        if line.isdigit():
            i += 1
            if i >= len(lines):
                break
            line = lines[i].strip()
            
        if "-->" in line:
            parts = line.split("-->")
            start_part = parts[0].strip()
            right_part = parts[1].strip()
            
            right_split = right_part.split(maxsplit=1)
            end_part = right_split[0].strip()
            text_lines = []
            if len(right_split) > 1:
                text_lines.append(right_split[1].strip())
                
            i += 1
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    break
                if next_line.isdigit():
                    break
                if "-->" in next_line:
                    break
                text_lines.append(next_line)
                i += 1
                
            start_time = sanitize_time(start_part)
            end_time = sanitize_time(end_part)
            text_content = " ".join(text_lines).strip()
            
            blocks.append({
                'index': len(blocks) + 1,
                'start': start_time,
                'end': end_time,
                'text': text_content
            })
        else:
            i += 1
            
    output_lines = []
    for b in blocks:
        output_lines.append(f"{b['index']}\n{b['start']} --> {b['end']}\n{b['text']}\n\n")
        
    return "".join(output_lines)


def get_ffmpeg_safe_path(path):
    abs_path = os.path.abspath(path)
    abs_path_forward = abs_path.replace("\\", "/")
    safe_path = abs_path_forward.replace(":", "\\\\:").replace(" ", "\\\\ ")
    return safe_path


def stabilize_centers(raw_centers, threshold=40):
    if not raw_centers:
        return []
    stable = [raw_centers[0]]
    for x in raw_centers[1:]:
        last = stable[-1]
        if abs(x - last) > threshold:
            stable.append(x)
        else:
            stable.append(last)
    return stable


def make_nested_if(centers):
    if not centers:
        return "0"
    expr = str(centers[-1])
    for i in range(len(centers) - 2, -1, -1):
        expr = f"if(lt(t,{i+1}),{centers[i]},{expr})"
    return expr


def highlight_srt_content(srt_text, highlight_color="Neon Yellow"):
    def srt_time_to_secs(t_str):
        t_str = t_str.strip().replace('.', ',')
        parts = t_str.split(':')
        hh = int(parts[0])
        mm = int(parts[1])
        ss_mmm = parts[2]
        ss, mmm = ss_mmm.split(',')
        return hh * 3600 + mm * 60 + int(ss) + int(mmm) / 1000.0

    def secs_to_srt_time(secs):
        if secs < 0:
            secs = 0
        hh = int(secs // 3600)
        mm = int((secs % 3600) // 60)
        ss = int(secs % 60)
        mmm = int(round((secs - int(secs)) * 1000))
        if mmm >= 1000:
            mmm = 999
        return f"{hh:02d}:{mm:02d}:{ss:02d},{mmm:03d}"

    color_map = {
        "Neon Yellow": "#FFFF00",
        "Neon Green": "#00FF00",
        "Neon Pink": "#FF007F",
        "Cyan": "#00FFFF",
        "Vibrant Orange": "#FF6600"
    }
    color_cycle = ["#FFFF00", "#00FF00", "#FF007F", "#00FFFF", "#FF6600"]

    fixed_srt = fix_srt_content(srt_text)
    raw_blocks = fixed_srt.strip().split("\n\n")
    new_blocks = []
    block_idx = 1
    
    for rb in raw_blocks:
        lines = [line.strip() for line in rb.strip().split("\n") if line.strip()]
        if len(lines) < 3:
            continue
            
        time_line_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_line_idx = idx
                break
        
        if time_line_idx == -1:
            continue
            
        times = lines[time_line_idx].split("-->")
        if len(times) != 2:
            continue
            
        start_str = times[0].strip()
        end_str = times[1].strip()
        text = " ".join(lines[time_line_idx+1:]).strip()
        text = text.upper()
        
        try:
            start_secs = srt_time_to_secs(start_str)
            end_secs = srt_time_to_secs(end_str)
        except Exception:
            continue
            
        words = text.split()
        if not words:
            continue
            
        N = len(words)
        duration = end_secs - start_secs
        
        if N == 1 or duration <= 0:
            if highlight_color == "Multi-Color Cycle":
                active_color = color_cycle[block_idx % len(color_cycle)]
            else:
                active_color = color_map.get(highlight_color, "#FFFF00")
            highlighted_text = f'<font color="{active_color}">{words[0]}</font>'
            new_blocks.append({
                'index': block_idx,
                'start': start_str,
                'end': end_str,
                'text': highlighted_text
            })
            block_idx += 1
        else:
            dt = duration / N
            for i in range(N):
                s_i = start_secs + i * dt
                e_i = start_secs + (i + 1) * dt
                
                highlighted_words = []
                for w_idx, w in enumerate(words):
                    if w_idx == i:
                        if highlight_color == "Multi-Color Cycle":
                            active_color = color_cycle[(block_idx + w_idx) % len(color_cycle)]
                        else:
                            active_color = color_map.get(highlight_color, "#FFFF00")
                        highlighted_words.append(f'<font color="{active_color}">{w}</font>')
                    else:
                        highlighted_words.append(w)
                highlighted_text = " ".join(highlighted_words)
                
                new_blocks.append({
                    'index': block_idx,
                    'start': secs_to_srt_time(s_i),
                    'end': secs_to_srt_time(e_i),
                    'text': highlighted_text
                })
                block_idx += 1
                
    output_lines = []
    for b in new_blocks:
        output_lines.append(f"{b['index']}\n{b['start']} --> {b['end']}\n{b['text']}\n\n")
    return "".join(output_lines)


def crop_and_burn_title(input_path, title_text, api_key, model, output_path, highlight_color="Neon Yellow"):
    """Crops horizontal video to vertical with tight face tracking, 12% zoom cuts, and highlighted subtitles in one pass."""
    ensure_ffmpeg_in_path()
    import cv2
    import numpy as np
    import subprocess
    import textwrap
    import uuid
    import os

    print(f"Starting combined vertical crop & subtitle burn for: '{input_path}'...")
    input_base = os.path.splitext(os.path.basename(input_path))[0]
    
    # Spelling corrections (for fallback subtitles if used)
    title_text = title_text.replace("PHENIX", "PHOENIX").replace("Phenix", "Phoenix").replace("phenix", "phoenix")
    
    # 1. Get video width, height, and FPS using OpenCV
    cap = cv2.VideoCapture(input_path)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    
    # 2. Run face detection auto-reframe to locate face center x-coordinates
    print("Scanning video frames for face tracking auto-reframe...")
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    raw_centers = []
    last_known_x = w // 2
    frame_interval = int(round(fps))
    
    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(30, 30))
            
            if len(faces) > 0:
                largest_face = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = largest_face
                face_center_x = int((fx + fw / 2) * 2)
                last_known_x = face_center_x
                raw_centers.append(face_center_x)
            else:
                raw_centers.append(last_known_x)
                
        frame_count += 1
    cap.release()
    
    if not raw_centers:
        raw_centers = [w // 2]
        
    # Stabilize centers to avoid jitter, cuts only on large shifts
    stable_centers = stabilize_centers(raw_centers, threshold=40)
    face_x_expr = make_nested_if(stable_centers)
    
    # Crop dimensions calculations for vertical podcast framing (9:16 layout)
    target_ratio = 9 / 16
    crop_h = int(round(h / 1.2))  # Optimal podcast framing (1.2x base zoom)
    crop_w = int(round(crop_h * target_ratio))
    crop_h = (crop_h // 2) * 2
    crop_w = (crop_w // 2) * 2
    
    if crop_w > w:
        crop_w = (w // 2) * 2
        crop_h = int(round(crop_w / target_ratio))
        crop_h = (crop_h // 2) * 2
    if crop_h > h:
        crop_h = (h // 2) * 2
        crop_w = int(round(crop_h * target_ratio))
        crop_w = (crop_w // 2) * 2
        
    # 3. Extract audio stream for Gemini transcription
    print("Extracting audio stream for transcription...")
    temp_dir = os.path.dirname(output_path)
    audio_path = os.path.join(temp_dir, f"temp_audio_{input_base}.m4a")
    
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "copy", audio_path
    ], capture_output=True)
    
    # 4. Transcribe and generate SRT timed subtitles with Gemini API (with fallback)
    mock_srt_content = f"1\n00:00:00,100 --> 00:00:04,000\n{title_text}\n"
    srt_content = None
    
    if api_key:
        try:
            print("Uploading audio to Gemini for timed captions...")
            from google import genai
            client = genai.Client(api_key=api_key)
            audio_file = client.files.upload(file=audio_path)
            print("Upload complete. Generating word-by-word subtitles...")
            
            prompt = (
                "You are an expert social media and podcast video editor. Listen to this audio clip. "
                "If the audio is in Hindi or any other non-English language, translate it directly to English. "
                "Transcribe the audio (in English translation) and generate a standard SRT subtitle file. "
                "To make the captions look extremely engaging like modern TikTok/Shorts captions, follow these rules: "
                "1. Every subtitle entry MUST contain strictly 1 to 3 words. "
                "2. The duration of each subtitle must be very short (e.g. 0.3s to 0.8s) matching the voice exactly. "
                "3. Every word must be in UPPERCASE. "
                "4. Do NOT group large blocks of text. Make the words flash rapidly on the screen. "
                "5. Output ONLY the raw, valid SRT subtitle content in English translation. No explanation, no markdown tags."
            )
            
            response = client.models.generate_content(
                model=model,
                contents=[audio_file, prompt]
            )
            srt_content = response.text.strip()
            
            try:
                client.files.delete(name=audio_file.name)
            except:
                pass
        except Exception as e:
            print(f"Warning: Gemini API call failed ({e}). Falling back to mock subtitles.")
            srt_content = mock_srt_content
    else:
        print("Warning: Gemini API key not found. Using mock subtitles.")
        srt_content = mock_srt_content
        
    if not srt_content:
        srt_content = mock_srt_content
        
    # Robustly clean markdown wrappers and conversational prefix/suffix
    srt_content = clean_markdown_srt(srt_content)
        
    # Highlight individual active words in subtitle content
    highlighted_srt = highlight_srt_content(srt_content, highlight_color=highlight_color)
    
    # Save SRT to a temp file
    srt_path = os.path.join(temp_dir, f"subs_{input_base}.srt").replace("\\", "/")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(highlighted_srt)
        
    # 5. Build top hook title tagline file (relative path to avoid colon escaping bugs)
    lines = textwrap.wrap(title_text, width=28)
    wrapped_title = "\n".join(lines)
    max_line_len = max(len(l) for l in lines) if lines else 1
    
    # Calculate dynamic font size based on 1080px scale
    calculated_font_size = int((1080 * 0.85) / (max_line_len * 0.6))
    font_size = max(min(calculated_font_size, 72), 48)
    
    relative_title_path = f"temp_title_{input_base}.txt"
    with open(relative_title_path, "w", encoding="utf-8") as f:
        f.write(wrapped_title)
        
    # 6. Format path for FFmpeg subtitles filter
    safe_srt_path = get_ffmpeg_safe_path(srt_path)
    
    # Parse SRT blocks to align camera punch-in cuts to word starts
    subtitle_starts = []
    for rb in highlighted_srt.strip().split("\n\n"):
        lines = [line.strip() for line in rb.strip().split("\n") if line.strip()]
        if len(lines) < 2:
            continue
        time_line = None
        for line in lines:
            if "-->" in line:
                time_line = line
                break
        if not time_line:
            continue
        start_part = time_line.split("-->")[0].strip()
        try:
            parts = start_part.split(':')
            hh = int(parts[0])
            mm = int(parts[1])
            ss, mmm = parts[2].split(',')
            secs = hh * 3600 + mm * 60 + int(ss) + int(mmm) / 1000.0
            subtitle_starts.append(secs)
        except Exception:
            continue
            
    # Calculate cuts aligned to word starts approximately every 4 seconds
    cut_times = []
    target_cut = 4.0
    for start in subtitle_starts:
        if start >= target_cut:
            cut_times.append(round(start, 3))
            target_cut = start + 4.0
            
    # Generate nested conditional zoom expression matching cut times (normal zoom = 1.0, punch-in = 1.12)
    def make_zoom_if(cuts):
        if not cuts:
            return "1.0"
        default_val = "1.12" if len(cuts) % 2 == 1 else "1.0"
        expr = default_val
        for idx in range(len(cuts) - 1, -1, -1):
            val = "1.12" if idx % 2 == 1 else "1.0"
            expr = f"if(lt(t,{cuts[idx]}),{val},{expr})"
        return expr
        
    zoom_expr = make_zoom_if(cut_times)
    print(f"Word-aligned zoom cuts scheduled at {cut_times}")
    
    # FFmpeg filtergraph:
    # 1. Scale input dynamically based on zoom_expr
    # 2. Crop input dynamically centering on face_x_expr
    # 3. Scale output to standard high-quality vertical 1080x1920 canvas
    # 4. Drawtext for top tagline hook title (Arial, yellow, outline, y=230 to clear device safe zones)
    # 5. Burn subtitles with highlights (Impact, white base text with Outline=3.0, Alignment=2, MarginV=640)
    vf_filter = (
        f"scale=w='trunc(iw*{zoom_expr}/2)*2':h='trunc(ih*{zoom_expr}/2)*2':eval=frame,"
        f"crop={crop_w}:{crop_h}:'clip({face_x_expr}*{zoom_expr}-{crop_w}/2,0,iw-{crop_w})':'(ih-{crop_h})/2',"
        f"scale=1080:1920,"
        f"drawtext=textfile='{relative_title_path}':font='Arial':fontsize={font_size}:fontcolor=yellow:borderw=4:bordercolor=black:x=(w-text_w)/2:y=230,"
        f"subtitles={safe_srt_path}:force_style='Fontname=Impact,Fontsize=54,PrimaryColour=&H00FFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3.0,Alignment=2,MarginV=640'"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", "superfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path
    ]
    
    try:
        print(f"Executing combined FFmpeg crop, zoom & subtitle burn: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError(f"Combined FFmpeg process failed: {result.stderr}")
    finally:
        # Clean up temp SRT file, tagline file, and audio file
        for path in [srt_path, relative_title_path, audio_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except:
                    pass
                    
    print(f"Rendered production vertical video with captions: {output_path}")
    return output_path
