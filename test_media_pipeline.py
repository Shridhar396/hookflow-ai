import os
import sys
import utils

def main():
    print("=== Testing Media Processing Pipeline ===")
    
    # 1. Ensure FFmpeg is configured
    utils.ensure_ffmpeg_in_path()
    
    # Use Keyboard Cat as a lightweight test video (~54 seconds long)
    test_url = "https://www.youtube.com/watch?v=J---aiyznGQ"
    
    # Create a test output directory
    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "test_output"))
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        print(f"Created test directory: {test_dir}")
        
    raw_clip_path = os.path.join(test_dir, "raw_clip.mp4")
    cropped_clip_path = os.path.join(test_dir, "cropped_clip.mp4")
    
    # Remove older test files if they exist
    for p in [raw_clip_path, cropped_clip_path]:
        if os.path.exists(p):
            os.remove(p)
            
    # Try fetching metadata
    print("\n1. Fetching video metadata...")
    try:
        info = utils.get_video_info(test_url)
        print(f"Success! Video Title: {info['title']}")
        print(f"Duration: {info['duration']} seconds")
    except Exception as e:
        print(f"Error fetching metadata: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Download a 5-second slice (from 5.0 to 10.0 seconds)
    start_secs = 5.0
    end_secs = 10.0
    print(f"\n2. Downloading 5-second video segment ({start_secs}s - {end_secs}s)...")
    try:
        utils.download_video_range(test_url, start_secs, end_secs, raw_clip_path)
        if os.path.exists(raw_clip_path) and os.path.getsize(raw_clip_path) > 0:
            print(f"Success! Raw clip saved to: {raw_clip_path} ({os.path.getsize(raw_clip_path)} bytes)")
        else:
            print("Failed to download clip or file is empty.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error downloading segment: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Crop the video to vertical
    print("\n3. Cropping clip to vertical (9:16) format using MoviePy...")
    try:
        utils.crop_to_vertical(raw_clip_path, cropped_clip_path)
        if os.path.exists(cropped_clip_path) and os.path.getsize(cropped_clip_path) > 0:
            print(f"Success! Cropped clip saved to: {cropped_clip_path} ({os.path.getsize(cropped_clip_path)} bytes)")
        else:
            print("Failed to crop clip or output is empty.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error cropping clip: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Burn title onto the video
    burned_clip_path = os.path.join(test_dir, "burned_clip.mp4")
    if os.path.exists(burned_clip_path):
        os.remove(burned_clip_path)
        
    print("\n4. Burning title 'KEYBOARD CAT REMIX' onto the vertical video...")
    try:
        utils.burn_title(cropped_clip_path, "KEYBOARD CAT REMIX", burned_clip_path)
        if os.path.exists(burned_clip_path) and os.path.getsize(burned_clip_path) > 0:
            print(f"Success! Burned clip saved to: {burned_clip_path} ({os.path.getsize(burned_clip_path)} bytes)")
        else:
            print("Failed to burn title or output is empty.", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error burning title: {e}", file=sys.stderr)
        sys.exit(1)
        
    print("\n=== All Media Processing Pipeline Tests Passed! ===")
    print(f"You can view the resulting vertical clip here: {burned_clip_path}")

if __name__ == "__main__":
    main()
