from fastapi import APIRouter, HTTPException
from app.services import embedding_service
from app.models.video_models import VideoUploadRequest, VideoProcessBatchResponse

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