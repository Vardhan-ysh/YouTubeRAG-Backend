from fastapi import APIRouter, HTTPException
from app.services import youtube_service, embeddings_service

router = APIRouter()

@router.post("/process")
async def process_videos(data: dict):
    """
    Accepts one or multiple YouTube URLs,
    fetches transcripts, and stores embeddings.
    """
    try:
        urls = data.get("urls")
        if not urls:
            raise HTTPException(status_code=400, detail="No URLs provided")

        # Placeholder service call
        results = await youtube_service.process_videos(urls)

        return {"message": "Videos processed successfully", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
