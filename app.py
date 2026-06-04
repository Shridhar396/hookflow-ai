import os
import sys
import shutil
import streamlit as st
from dotenv import load_dotenv
load_dotenv()  # Load variables from .env
import utils

# Set page configuration
st.set_page_config(
    page_title="Viral Shorts Generator - YouTube Shorts Extractor",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern dark glassmorphic design and interactions
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', sans-serif;
        background: linear-gradient(135deg, #090714 0%, #110c24 50%, #06040a 100%) !important;
        color: #e2e8f0 !important;
    }
    
    /* Header styling */
    .header-container {
        display: flex;
        align-items: center;
        margin-bottom: 1.5rem;
        gap: 0.75rem;
    }
    
    .app-title {
        font-size: 2.75rem;
        font-weight: 800;
        background: linear-gradient(90deg, #ff007f 0%, #7f00ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    
    .app-subtitle {
        font-size: 1.05rem;
        color: #94a3b8;
        margin-bottom: 2rem;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0b0918 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Sleek Cards */
    .custom-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.5rem;
        backdrop-filter: blur(12px);
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.15);
    }
    
    .card-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: #f1f5f9;
        margin-bottom: 0.75rem;
    }
    
    /* Interactive Clip Cards (Inactive) */
    .clip-card {
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
        cursor: pointer;
    }
    
    .clip-card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: rgba(255, 255, 255, 0.12);
        transform: translateY(-2px);
    }
    
    /* Clip Cards (Active Selection) */
    .clip-card-active {
        background: rgba(127, 0, 255, 0.06) !important;
        border: 1px solid #7f00ff !important;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        box-shadow: 0 0 15px rgba(127, 0, 255, 0.15);
    }
    
    /* Badges */
    .score-badge {
        background: linear-gradient(135deg, #ff007f 0%, #7f00ff 100%);
        color: white;
        font-size: 0.8rem;
        font-weight: 700;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        display: inline-block;
        margin-bottom: 0.5rem;
    }
    
    /* Custom rendering button */
    div.stButton > button {
        background: linear-gradient(90deg, #ff007f 0%, #7f00ff 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.5rem 1.25rem !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 14px rgba(127, 0, 255, 0.3) !important;
        transition: all 0.25s ease !important;
        width: 100% !important;
    }
    div.stButton > button:hover {
        box-shadow: 0 6px 18px rgba(255, 0, 127, 0.5) !important;
        transform: scale(1.02) !important;
    }
    
    /* Outline minor buttons */
    .secondary-btn button {
        background: transparent !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        box-shadow: none !important;
    }
    .secondary-btn button:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
        box-shadow: none !important;
    }
    
    /* Inputs */
    input {
        background-color: #120e26 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 8px !important;
        color: white !important;
    }
    
    .stProgress > div > div > div > div {
        background-color: #7f00ff !important;
    }
</style>
""", unsafe_allow_html=True)

# State Management Initialization
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False
if "clips" not in st.session_state:
    st.session_state.clips = []
if "video_info" not in st.session_state:
    st.session_state.video_info = None
if "selected_clip_idx" not in st.session_state:
    st.session_state.selected_clip_idx = 0
if "rendered_clips" not in st.session_state:
    # Maps clip_index to output file path
    st.session_state.rendered_clips = {}
if "last_url" not in st.session_state:
    st.session_state.last_url = ""

# Helper to check FFmpeg
def get_ffmpeg_status():
    project_dir = os.path.abspath(os.path.dirname(__file__))
    bin_dir = os.path.join(project_dir, "bin")
    ffmpeg_local = os.path.join(bin_dir, "ffmpeg.exe")
    ffprobe_local = os.path.join(bin_dir, "ffprobe.exe")
    
    if os.path.exists(ffmpeg_local) and os.path.exists(ffprobe_local):
        return "Local (Prebuilt Binaries Folder)"
    elif shutil.which("ffmpeg") is not None:
        return "System PATH (Found)"
    else:
        return "Missing (Download Required)"

# Clear states when URL changes
def reset_state_for_new_url(new_url):
    if st.session_state.last_url != new_url:
        st.session_state.last_url = new_url
        st.session_state.analysis_done = False
        st.session_state.clips = []
        st.session_state.video_info = None
        st.session_state.selected_clip_idx = 0
        st.session_state.rendered_clips = {}
        # Clear temp files
        temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp"))
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
            os.makedirs(temp_dir)

# Setup Workspace Dir
temp_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "temp"))
if not os.path.exists(temp_dir):
    os.makedirs(temp_dir)

# Header Section
st.markdown("""
<div class='header-container'>
    <h1 class='app-title'>🎬 Viral Shorts Generator</h1>
</div>
""", unsafe_allow_html=True)
st.markdown("<p class='app-subtitle'>Find the Top 3 viral moments from YouTube videos, crop to vertical (9:16), and burn hook titles automatically.</p>", unsafe_allow_html=True)

# Sidebar settings
st.sidebar.markdown("### ⚙️ Workspace Configuration")

selected_model = st.sidebar.selectbox(
    "Gemini Model",
    ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
    help="gemini-2.5-flash is fast, cost-effective, and excellent at audio transcription."
)

api_key = st.sidebar.text_input(
    "Gemini API Key",
    value=os.environ.get("GEMINI_API_KEY", ""),
    type="password",
    help="Leave blank if GEMINI_API_KEY environment variable is set."
)

num_clips = st.sidebar.slider(
    "Number of Shorts to Extract",
    min_value=1,
    max_value=5,
    value=3,
    help="Select how many viral shorts segments you want the AI to extract."
)

ffmpeg_status = get_ffmpeg_status()
st.sidebar.markdown(f"**FFmpeg Status:** `{ffmpeg_status}`")

if ffmpeg_status == "Missing (Download Required)":
    st.sidebar.warning("FFmpeg and FFprobe are required to trim and crop videos.")
    if st.sidebar.button("⬇️ Setup local FFmpeg"):
        with st.sidebar.spinner("Downloading FFmpeg binaries..."):
            try:
                import subprocess
                result = subprocess.run([sys.executable, "download_ffmpeg.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
                if result.returncode == 0:
                    st.sidebar.success("FFmpeg successfully set up!")
                    st.rerun()
                else:
                    st.sidebar.error(f"Setup failed: {result.stderr}")
            except Exception as e:
                st.sidebar.error(f"Error: {e}")

# Screen Split Columns
col_left, col_right = st.columns([5, 7], gap="medium")

# LEFT PANEL: URL pasting, metadata cards, and clip cards list
with col_left:
    st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
    st.markdown("<div class='card-title'>🔗 YouTube URL</div>", unsafe_allow_html=True)
    url_input = st.text_input(
        "Paste YouTube video URL here:",
        placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed"
    )
    st.markdown("</div>", unsafe_allow_html=True)
    
    if url_input:
        # Reset if it's a new link
        reset_state_for_new_url(url_input)
        
        # Load video metadata card
        if st.session_state.video_info is None:
            try:
                with st.spinner("Fetching YouTube metadata..."):
                    st.session_state.video_info = utils.get_video_info(url_input)
            except Exception as e:
                st.error(f"Error fetching YouTube metadata: {e}")
                
        # If metadata is successfully loaded
        if st.session_state.video_info:
            info = st.session_state.video_info
            
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            c_thumb, c_meta = st.columns([4, 6])
            with c_thumb:
                if info.get('thumbnail'):
                    st.image(info['thumbnail'], use_column_width=True)
            with c_meta:
                st.markdown(f"**Title:** {info['title']}")
                mins = f"{info['duration'] // 60}m {info['duration'] % 60}s" if info['duration'] else "Unknown"
                st.markdown(f"**Duration:** {mins}")
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Action button for analysis
            if not st.session_state.analysis_done:
                analyze_clicked = st.button(f"🔍 Analyze Viral Moments (Extract {num_clips} clips)")
                if analyze_clicked:
                    if not api_key:
                        st.error("Please enter a Gemini API Key in the sidebar or set the GEMINI_API_KEY environment variable.")
                    else:
                        progress_box = st.empty()
                        progress_bar = st.progress(0)
                        
                        try:
                            # Step 1: Download Audio
                            progress_box.info("Step 1 of 2: Downloading audio stream...")
                            progress_bar.progress(25)
                            audio_path = utils.download_audio(url_input, temp_dir)
                            
                            # Step 2: Query Gemini for Clips
                            progress_box.info("Step 2 of 2: Gemini is transcribing & analyzing audio for viral clips...")
                            progress_bar.progress(65)
                            result_data = utils.find_viral_clip(audio_path, api_key, num_clips=num_clips, model=selected_model)
                            
                            st.session_state.clips = result_data.get("clips", [])
                            st.session_state.analysis_done = True
                            
                            progress_bar.progress(100)
                            progress_box.success("Analysis complete!")
                            st.rerun()
                        except Exception as e:
                            progress_bar.empty()
                            progress_box.empty()
                            err_msg = str(e)
                            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                                st.error("🚨 Gemini API Quota Exceeded (429). The server's key has reached its limit. To continue, please enter your own Gemini API Key in the sidebar.")
                            else:
                                st.error(f"Analysis failed: {e}")
            
            # Render Clip cards list
            if st.session_state.analysis_done and st.session_state.clips:
                st.markdown("### 🗂️ Identified Clips")
                st.caption("Click a card to view details. Render them one by one below.")
                
                for idx, clip in enumerate(st.session_state.clips):
                    # Check selection state
                    is_active = (st.session_state.selected_clip_idx == idx)
                    card_class = "clip-card-active" if is_active else "clip-card"
                    
                    # Custom interactive card using markdown + custom css
                    st.markdown(f"""
                    <div class='{card_class}'>
                        <span class='score-badge'>🔥 Virality Score: {clip['virality_score']}%</span>
                        <div style='font-weight: 700; font-size: 1.1rem; color: #f1f5f9; margin-bottom: 0.25rem;'>
                            #{idx+1}: {clip['title']}
                        </div>
                        <div style='font-size: 0.85rem; color: #94a3b8;'>
                            ⏱️ Duration: {clip['start_time']} - {clip['end_time']} ({round(clip['end_seconds'] - clip['start_seconds'], 1)}s)
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Sub-layout buttons under each card for activation and rendering
                    btn_cols = st.columns([1, 1])
                    with btn_cols[0]:
                        # Make this secondary-btn style
                        st.markdown("<div class='secondary-btn'>", unsafe_allow_html=True)
                        if st.button(f"👁️ View Details", key=f"select_clip_{idx}"):
                            st.session_state.selected_clip_idx = idx
                            st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    with btn_cols[1]:
                        # Check if already rendered
                        if idx in st.session_state.rendered_clips:
                            st.button(f"✅ Rendered", key=f"render_clip_{idx}", disabled=True)
                        else:
                            if st.button(f"Render Vertical Short (9:16) 🎬", key=f"render_clip_{idx}"):
                                # Ensure we select it first
                                st.session_state.selected_clip_idx = idx
                                
                                # Render process
                                render_status = st.empty()
                                render_progress = st.progress(0)
                                
                                import uuid
                                video_id = utils.extract_youtube_id(url_input)
                                transaction_uid = uuid.uuid4().hex[:8]
                                transaction_id = f"{video_id}_{transaction_uid}"
                                
                                raw_clip = os.path.join(temp_dir, f"video_{transaction_id}_raw_{idx}.mp4")
                                cropped_clip = os.path.join(temp_dir, f"video_{transaction_id}_cropped_{idx}.mp4")
                                final_output = os.path.join(temp_dir, f"viral_short_{video_id}_{idx}.mp4")
                                
                                try:
                                    # 1. Download range
                                    render_status.info("Step 1 of 3: Downloading segment stream...")
                                    render_progress.progress(20)
                                    utils.download_video_range(url_input, clip["start_seconds"], clip["end_seconds"], raw_clip)
                                    
                                    # 2. Crop
                                    render_status.info("Step 2 of 3: Cropping frame to 9:16 center...")
                                    render_progress.progress(55)
                                    utils.crop_to_vertical(raw_clip, cropped_clip)
                                    
                                    # 3. Subtitle overlay
                                    render_status.info("Step 3 of 3: Burning styled hook title...")
                                    render_progress.progress(85)
                                    utils.burn_title(cropped_clip, clip["title"].upper(), final_output)
                                    
                                    # Done
                                    render_progress.progress(100)
                                    render_status.success("Render complete!")
                                    
                                    st.session_state.rendered_clips[idx] = final_output
                                    st.rerun()
                                except Exception as e:
                                    render_progress.empty()
                                    err_msg = str(e)
                                    if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
                                        render_status.error("🚨 Gemini API Quota Exceeded (429). Please enter your own Gemini API Key in the sidebar to render.")
                                    else:
                                        render_status.error(f"Render failed: {e}")
                                finally:
                                    # Aggressively delete intermediate raw and cropped files
                                    for p in [raw_clip, cropped_clip]:
                                        if os.path.exists(p):
                                            try:
                                                os.remove(p)
                                                print(f"Purged intermediate file: {p}")
                                            except Exception:
                                                pass

# RIGHT PANEL: Detailed Workspace & Player
with col_right:
    if not st.session_state.analysis_done:
        st.markdown("<div class='custom-card' style='text-align: center; padding: 4rem 1.5rem;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 3rem;'>🎯</div>", unsafe_allow_html=True)
        st.markdown("<div class='card-title'>Viral Analysis Workspace</div>", unsafe_allow_html=True)
        st.markdown("<p class='card-text'>Input a YouTube URL and click <b>Analyze Viral Moments</b> on the left to start. The AI will segment the video and highlight the best clips.</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        active_idx = st.session_state.selected_clip_idx
        clip = st.session_state.clips[active_idx]
        
        # Display Workspace
        st.markdown(f"## 📋 Workspace: Clip #{active_idx+1}")
        
        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
        
        # Score and title
        c_score, c_title = st.columns([3, 7])
        with c_score:
            st.metric(label="Predicted Virality", value=f"{clip['virality_score']}%")
        with c_title:
            st.markdown(f"#### Hook Title: `{clip['title']}`")
            st.markdown(f"⏱️ **Time Range:** `{clip['start_time']} - {clip['end_time']}`")
            
        st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 1rem 0;'>", unsafe_allow_html=True)
        
        # Reasoning
        st.markdown("##### 🚀 virality reasoning")
        st.write(clip["reasoning"])
        
        # Transcript
        st.markdown("##### 📝 segment transcript")
        st.info(clip["transcript_segment"])
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Video Player Area
        st.markdown("### 🎥 Video Preview")
        if active_idx in st.session_state.rendered_clips:
            video_path = st.session_state.rendered_clips[active_idx]
            if os.path.exists(video_path):
                st.markdown("<div class='custom-card' style='text-align: center;'>", unsafe_allow_html=True)
                
                # Show video player (vertical orientation)
                st.video(video_path)
                
                # Download Button
                with open(video_path, "rb") as f:
                    st.download_button(
                        label="📥 Download Vertical Short",
                        data=f,
                        file_name=f"viral_short_{active_idx+1}.mp4",
                        mime="video/mp4",
                        key=f"download_{active_idx}"
                    )
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.warning("Video file not found. Please re-render.")
        else:
            st.markdown("<div class='custom-card' style='text-align: center;'>", unsafe_allow_html=True)
            st.markdown("<div class='card-title'>📺 Lightweight Raw Preview (Stage 1)</div>", unsafe_allow_html=True)
            st.caption(f"Playing raw source video at start time {clip['start_time']}")
            st.video(url_input, start_time=int(clip["start_seconds"]))
            st.markdown("</div>", unsafe_allow_html=True)

# FULL-WIDTH GALLERY: Show previews of all rendered shorts at the bottom
if st.session_state.analysis_done and st.session_state.rendered_clips:
    st.markdown("---")
    st.markdown("### 📦 Rendered Shorts Gallery")
    st.caption("Play, preview, and download all generated vertical shorts in your batch below:")
    
    rendered_items = st.session_state.rendered_clips
    clip_indices = list(rendered_items.keys())
    
    # Render in rows of up to 3 columns max
    for i in range(0, len(clip_indices), 3):
        chunk = clip_indices[i:i+3]
        cols = st.columns(len(chunk))
        for col_idx, clip_idx in enumerate(chunk):
            video_path = rendered_items[clip_idx]
            if os.path.exists(video_path):
                clip_details = st.session_state.clips[clip_idx]
                with cols[col_idx]:
                    st.markdown(f"<div class='custom-card' style='text-align: center;'>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-weight: 700; margin-bottom: 0.5rem;'>Clip #{clip_idx+1}: {clip_details['title']}</div>", unsafe_allow_html=True)
                    st.video(video_path)
                    
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label=f"📥 Download Short #{clip_idx+1}",
                            data=f,
                            file_name=f"viral_short_{clip_idx+1}.mp4",
                            mime="video/mp4",
                            key=f"gallery_download_{clip_idx}"
                        )
                    st.markdown("</div>", unsafe_allow_html=True)
