async def process_videos(urls: list[str]):
    # TODO: Fetch transcripts, translate, chunk, and send to embedding service
    return [{"url": url, "status": "pending"} for url in urls]
