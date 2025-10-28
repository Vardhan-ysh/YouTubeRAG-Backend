from fastapi import APIRouter
from app.routes.video import video_router
from app.routes.chat import chat_router

router = APIRouter()

router.include_router(video_router, prefix="/video")
router.include_router(chat_router, prefix="/chat")