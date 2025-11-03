from pydantic import BaseModel, Field
from typing import List, Optional

class VideoUploadRequest(BaseModel):
    urls: List[str] = Field(..., description="List of YouTube video URLs to process")

class VideoProcessResponse(BaseModel):
    video_id: Optional[str] = None
    url: str
    status: str  # "processing", "active", "error"
    chunks_count: Optional[int] = None
    message: str

class VideoProcessBatchResponse(BaseModel):
    results: List[VideoProcessResponse]