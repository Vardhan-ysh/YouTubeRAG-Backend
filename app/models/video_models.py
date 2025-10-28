from pydantic import BaseModel
from typing import List

class VideoUploadRequest(BaseModel):
    urls: List[str]

class VideoProcessResponse(BaseModel):
    video_id: str
    status: str