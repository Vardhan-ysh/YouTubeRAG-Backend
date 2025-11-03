from fastapi import APIRouter, HTTPException
from app.services import chat_service
from app.models.chat_model import ChatRequest, ChatResponse

chat_router = APIRouter()

@chat_router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest):
    """
    Query a video using RAG.
    
    The video must be processed first using the /video/process endpoint.
    Returns an answer based on the video transcript with source citations.
    """
    result = await chat_service.handle_chat(
        video_id=request.video_id,
        question=request.query,
        session_id=request.session_id
    )
    return result