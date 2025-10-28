from fastapi import APIRouter, HTTPException
from app.services import embedding_service

video_router = APIRouter()

@video_router.post("/process")
async def process_videos(data: dict):
    video_urls = data.get("urls", [])
    if not video_urls or not isinstance(video_urls, list):
        raise HTTPException(status_code=400, detail="Invalid or missing 'urls' field")
    results = await embedding_service.process_videos(video_urls)
    return {"results": results}