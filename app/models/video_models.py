from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class VideoUploadRequest(BaseModel):
    urls: List[str] = Field(..., description="List of YouTube video URLs to process")
    
    @field_validator('urls', mode='before')
    @classmethod
    def strip_urls(cls, v):
        """Strip whitespace and non-printable characters from URLs"""
        if isinstance(v, list):
            # Remove all whitespace and control characters
            cleaned = []
            for url in v:
                if isinstance(url, str):
                    # Keep only printable non-space characters
                    clean_url = ''.join(char for char in url if char.isprintable() and not char.isspace())
                    cleaned.append(clean_url)
                else:
                    cleaned.append(url)
            return cleaned
        return v

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