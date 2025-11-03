from fastapi import APIRouter, HTTPException
from app.services import embedding_service
from app.services import summary_service
from app.models.video_models import VideoUploadRequest, VideoProcessBatchResponse, VideoSummaryRequest, VideoSummaryResponse

video_router = APIRouter()

@video_router.post("/process", response_model=VideoProcessBatchResponse)
async def process_videos(request: VideoUploadRequest):
    """
    Process YouTube videos: fetch transcripts, generate embeddings, and store in database.
    
    Videos are cached for 1 day. If a video is already processed, it will return the existing status.
    
    Accepts:
    - urls: List of YouTube video URLs or video IDs
    
    Returns:
    - results: List of processing results for each video with status and metadata
    """
    results = await embedding_service.process_videos(request.urls)
    return {"results": results}

@video_router.post("/summary", response_model=VideoSummaryResponse)
async def get_video_summary(request: VideoSummaryRequest):
    """
    Generate a markdown summary of a processed video.
    
    The video must be processed first using the /video/process endpoint.
    
    Accepts:
    - video_id: YouTube video ID
    
    Returns:
    - video_id: The video ID
    - summary: Markdown-formatted comprehensive summary of the video
    - status: Processing status (success, not_found, processing, error)
    - message: Optional error or status message
    """
    result = await summary_service.generate_video_summary(request.video_id)
    return result