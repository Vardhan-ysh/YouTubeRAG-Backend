from fastapi import APIRouter, HTTPException
from app.services import rag_service

router = APIRouter()

@router.post("/query")
async def chat_query(data: dict):
    """
    Handles chat with a processed video.
    Performs RAG retrieval and response generation.
    """
    try:
        video_id = data.get("video_id")
        question = data.get("question")
        session_id = data.get("session_id")  # Optional for multi-turn chats

        if not video_id or not question:
            raise HTTPException(status_code=400, detail="Missing video_id or question")

        response = await rag_service.handle_chat(video_id, question, session_id)

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
