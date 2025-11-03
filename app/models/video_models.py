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

class VideoSummaryRequest(BaseModel):
    video_id: str = Field(..., description="YouTube video ID to summarize")

class SummarySourceChunk(BaseModel):
    chunk_index: int
    text: str
    start_time: float = 0.0
    end_time: float = 0.0
    url: str = ""
    video_id: str = ""

class VideoSummaryResponse(BaseModel):
    video_id: str
    summary: str  # Markdown formatted summary
    sources: List[SummarySourceChunk]  # All chunks used in the summary with metadata
    status: str  # "success", "not_found", "processing", "error"
    message: Optional[str] = None