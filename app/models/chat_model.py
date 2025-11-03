from pydantic import BaseModel, Field
from typing import List, Optional

class ChatRequest(BaseModel):
    query: str = Field(..., description="The user's question about the video")
    video_id: str = Field(..., description="The YouTube video ID to query")
    session_id: Optional[str] = Field(None, description="Optional session ID for conversation tracking")

class SourceChunk(BaseModel):
    chunk_index: int
    text: str
    similarity: float
    start_time: float = 0.0
    end_time: float = 0.0
    url: str = ""
    video_id: str = ""

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    status: str  # "success", "not_found", "processing", "error", "no_results"
    video_id: Optional[str] = None