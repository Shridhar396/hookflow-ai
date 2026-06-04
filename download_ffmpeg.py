import os
import urllib.request
import zipfile
import sys

FFMPEG_URL = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffmpeg-4.4.1-win-64.zip"
FFPROBE_URL = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffprobe-4.4.1-win-64.zip"

def download_and_extract(url, target_dir):
    filename = url.split("/")[-1]
    zip_path = os.path.join(target_dir, filename)
    
    print(f"Downloading {url}...")
    try:
        urllib.request.urlretrieve(url, zip_path)
        print(f"Downloaded {filename} successfully.")
    except Exception as e:
        print(f"Failed to download {filename}: {e}", file=sys.stderr)
        return False
        
    print(f"Extracting {filename}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(target_dir)
        print(f"Extracted {filename} successfully.")
    except Exception as e:
        print(f"Failed to extract {filename}: {e}", file=sys.stderr)
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
    return True

def setup_ffmpeg():
    project_dir = os.path.abspath(os.path.dirname(__file__))
    bin_dir = os.path.join(project_dir, "bin")
    
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)
        print(f"Created directory: {bin_dir}")
        
    ffmpeg_path = os.path.join(bin_dir, "ffmpeg.exe")
    ffprobe_path = os.path.join(bin_dir, "ffprobe.exe")
    
    success = True
    if not os.path.exists(ffmpeg_path):
        print("FFmpeg not found locally. Starting download...")
        success = success and download_and_extract(FFMPEG_URL, bin_dir)
    else:
        print("FFmpeg already exists locally.")
        
    if not os.path.exists(ffprobe_path):
        print("FFprobe not found locally. Starting download...")
        success = success and download_and_extract(FFPROBE_URL, bin_dir)
    else:
        print("FFprobe already exists locally.")
        
    if success:
        print(f"FFmpeg setup completed! Binaries are located in: {bin_dir}")
        # Verify execution
        print("Verifying FFmpeg...")
        os.system(f'"{ffmpeg_path}" -version')
    else:
        print("Failed to set up one or more FFmpeg binaries.", file=sys.stderr)

if __name__ == "__main__":
    setup_ffmpeg()
