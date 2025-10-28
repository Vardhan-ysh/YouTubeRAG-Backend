from fastapi import APIRouter, HTTPException
from app.services import chat_service

chat_router = APIRouter()

@chat_router.post("/query")
async def chat_query(data: dict):
    query = data.get("query", "")
    if not query or not isinstance(query, str):
        raise HTTPException(status_code=400, detail="Invalid or missing 'query' field")
    video_id = data.get("video_id", "")
    if not video_id or not isinstance(video_id, str):
        raise HTTPException(status_code=400, detail="Invalid or missing 'video_id' field")
    result = await chat_service.handle_chat(video_id, query)
    return {"result": result}