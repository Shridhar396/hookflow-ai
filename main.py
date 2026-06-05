import os
import shutil
import uuid
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

# Import the existing media processing pipeline
import utils

app = FastAPI(
    title="HookFlow AI API",
    description="Backend API for HookFlow AI, providing YouTube metadata extraction, viral clip analysis, and vertical video rendering.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://hookflow-ai-app.vercel.app",
        "https://hookflow-ai.vercel.app",
        "https://hookflow-ai-shridhardalvi24-6066s-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Models for Request/Response
class VideoInfoRequest(BaseModel):
    url: str

class AnalyzeRequest(BaseModel):
    url: str
    num_clips: int = 3
    api_key: Optional[str] = None
    model: str = "gemini-2.5-flash"

class RenderRequest(BaseModel):
    url: str
    clip_idx: int
    id: str
    start_time: str
    end_time: str
    start_seconds: float
    end_seconds: float
    title: str
    api_key: Optional[str] = None
    model: str = "gemini-2.5-flash"
    highlight_color: Optional[str] = "Neon Yellow"

# Stripe Simulation Models
class CheckoutSessionRequest(BaseModel):
    plan_name: str
    price: float
    success_url: str
    cancel_url: str

class CheckoutSessionResponse(BaseModel):
    session_id: str
    checkout_url: str

class StripeWebhookRequest(BaseModel):
    event_type: str
    session_id: str
    plan_name: str

# Helper: Get Gemini API Key
def get_gemini_api_key(provided_key: Optional[str]) -> str:
    key = provided_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise HTTPException(
            status_code=400,
            detail="Gemini API Key is missing. Please provide it in the request or set the GEMINI_API_KEY environment variable on the server."
        )
    return key

# Endpoints
@app.get("/api/health")
def health_check():
    ffmpeg_status = utils.get_ffmpeg_status() if hasattr(utils, "get_ffmpeg_status") else "Checked in utils"
    return {
        "status": "healthy",
        "app": "HookFlow AI API",
        "ffmpeg": ffmpeg_status
    }

@app.post("/api/video-info")
def post_video_info(req: VideoInfoRequest):
    try:
        info = utils.get_video_info(req.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch YouTube metadata: {str(e)}")

@app.post("/api/analyze")
def post_analyze(req: AnalyzeRequest):
    api_key = get_gemini_api_key(req.api_key)
    try:
        # Dynamically assign and clean the URL directly from the payload object
        video_url = req.url.strip()
        
        # Analyze using fast transcript path or internal fallback
        result = utils.find_viral_clip(
            url_or_path=video_url,
            api_key=api_key,
            num_clips=req.num_clips,
            model=req.model,
            temp_dir=TEMP_DIR
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini AI viral analysis failed: {str(e)}")

@app.post("/api/render")
def post_render(req: RenderRequest):
    raw_clip_path = None
    final_output_path = None
    try:
        # 1. Dynamically assign URL directly from payload, clean it
        video_url = req.url.strip()
        
        # 2. Extract unique YouTube Video ID
        video_id = utils.extract_youtube_id(video_url)
        
        # Create a unique alphanumeric UUID transaction ID
        transaction_uid = uuid.uuid4().hex[:8]
        
        # Use transaction ID for intermediate file, but keep stable clip filename for frontend caching
        raw_clip_filename = f"video_{video_id}_{transaction_uid}_{req.clip_idx}.mp4"
        final_clip_filename = f"clip_{video_id}_{req.clip_idx}.mp4"
        
        raw_clip_path = os.path.join(TEMP_DIR, raw_clip_filename)
        final_output_path = os.path.join(TEMP_DIR, final_clip_filename)
        
        # Get Gemini API Key
        api_key = get_gemini_api_key(req.api_key)
        
        # Step 1: Download range to raw video_{video_id}_{transaction_uid}_{clip_idx}.mp4
        utils.download_video_range(
            url=video_url,
            start_secs=req.start_seconds,
            end_secs=req.end_seconds,
            output_path=raw_clip_path
        )
        
        # Step 2: Crop to vertical 9:16 and burn hook title in a single pass using FFmpeg & Gemini
        utils.crop_and_burn_title(
            input_path=raw_clip_path,
            title_text=req.title.upper(),
            api_key=api_key,
            model=req.model,
            output_path=final_output_path,
            highlight_color=req.highlight_color
        )
        
        return {
            "success": True,
            "filename": final_clip_filename,
            "message": "Render completed successfully."
        }
        
    except Exception as e:
        # Clean up final output if rendering failed halfway
        if final_output_path and os.path.exists(final_output_path):
            try:
                os.remove(final_output_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Video rendering pipeline failed: {str(e)}")
    finally:
        # Aggressively delete intermediate raw video source file in all cases
        if raw_clip_path and os.path.exists(raw_clip_path):
            try:
                os.remove(raw_clip_path)
                print(f"Aggressively cleaned up intermediate raw clip: {raw_clip_path}")
            except Exception as cleanup_err:
                print(f"Warning: Failed to clean up raw clip {raw_clip_path}: {cleanup_err}")


@app.get("/api/stream/{filename}")
def stream_video(filename: str):
    file_path = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested video file not found.")
    
    return FileResponse(file_path, media_type="video/mp4")

@app.get("/api/download/{filename}")
def download_video(filename: str):
    file_path = os.path.join(TEMP_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Requested video file not found.")
    
    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# --- Stripe Sandbox Simulation Endpoints ---

# Temporary mock in-memory db for payments
stripe_mock_sessions = {}
user_subscriptions = {
    "default_user": {
        "plan": "Free",
        "credits": 3,
        "active": True
    }
}

@app.post("/api/stripe/create-checkout-session", response_model=CheckoutSessionResponse)
def create_checkout_session(req: CheckoutSessionRequest):
    session_id = f"cs_test_{uuid.uuid4().hex}"
    
    # In a real app, this redirects to stripe checkout. We will redirect to a simulated payment portal page in Next.js or return mock URLs.
    # We will simulate the checkout session in memory
    stripe_mock_sessions[session_id] = {
        "plan_name": req.plan_name,
        "price": req.price,
        "success_url": req.success_url,
        "cancel_url": req.cancel_url,
        "status": "pending"
    }
    
    # We will return a simulated URL path on the frontend
    checkout_url = f"/billing/checkout?session_id={session_id}&plan={req.plan_name}&price={req.price}"
    
    return CheckoutSessionResponse(
        session_id=session_id,
        checkout_url=checkout_url
    )

@app.post("/api/stripe/webhook")
def stripe_webhook(req: StripeWebhookRequest):
    """Simulates a Stripe webhook call that fulfills the subscription."""
    session_id = req.session_id
    if session_id in stripe_mock_sessions:
        stripe_mock_sessions[session_id]["status"] = "completed"
        
    # Update local in-memory subscription mock
    plan_name = req.plan_name
    credits = 3
    if plan_name == "Creator":
        credits = 60
    elif plan_name == "Pro":
        credits = 999999  # Unlimited
        
    user_subscriptions["default_user"] = {
        "plan": plan_name,
        "credits": credits,
        "active": True,
        "session_id": session_id
    }
    
    return {
        "received": True,
        "status": "subscription_activated",
        "user_subscription": user_subscriptions["default_user"]
    }

@app.get("/api/stripe/subscription")
def get_subscription_status():
    """Returns subscription details for the default simulated user."""
    return user_subscriptions.get("default_user", {
        "plan": "Free",
        "credits": 3,
        "active": True
    })

@app.post("/api/stripe/reset-credits")
def reset_subscription():
    """Resets simulated user back to Free tier for testing."""
    user_subscriptions["default_user"] = {
        "plan": "Free",
        "credits": 3,
        "active": True
    }
    return user_subscriptions["default_user"]

if __name__ == "__main__":
    import uvicorn
    # Use 0.0.0.0 for compatibility inside containers or local network testing
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
