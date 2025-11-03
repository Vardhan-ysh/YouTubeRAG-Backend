from youtube_transcript_api import YouTubeTranscriptApi
from app.utils.embedding_client import get_embeddings
from app.utils.supabase_client import (
    save_video_embeddings, 
    get_video_status,
    mark_video_processing,
    mark_video_complete,
    supabase
)
import re
from datetime import datetime, timedelta

def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # If no pattern matches, assume the input is already a video ID
    return url

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
    
    return chunks

async def process_videos(urls: list[str]):
    """
    Process YouTube videos: fetch transcripts, chunk, generate embeddings, and store in Supabase
    """
    results = []
    ytt_api = YouTubeTranscriptApi()
    
    for url in urls:
        video_id = None
        try:
            video_id = extract_video_id(url)
            
            # Check if video already exists
            status = get_video_status(video_id)
            if status in ["processing", "active"]:
                results.append({
                    "video_id": video_id,
                    "url": url,
                    "status": status,
                    "message": f"Video is already {status}"
                })
                continue
            
            # Mark as processing
            mark_video_processing(video_id)
            
            # Fetch transcript
            transcript = ytt_api.fetch(video_id, languages=['en'])
            
            # Build text with timing information
            # Create a mapping of character position to timing info
            full_text = ""
            timing_map = []  # List of (start_pos, end_pos, start_time, duration)
            
            for snippet in transcript:
                start_pos = len(full_text)
                full_text += snippet.text + " "
                end_pos = len(full_text) - 1
                timing_map.append({
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "start_time": snippet.start,
                    "duration": snippet.duration
                })
            
            # Chunk the text and associate timing info with each chunk
            raw_chunks = chunk_text(full_text, chunk_size=1000, overlap=200)
            
            # For each chunk, find the relevant timing information
            chunks_with_metadata = []
            for chunk in raw_chunks:
                chunk_start = full_text.find(chunk)
                chunk_end = chunk_start + len(chunk)
                
                # Find all snippets that overlap with this chunk
                relevant_timings = []
                for timing in timing_map:
                    if timing["start_pos"] < chunk_end and timing["end_pos"] > chunk_start:
                        relevant_timings.append({
                            "start": timing["start_time"],
                            "duration": timing["duration"]
                        })
                
                chunks_with_metadata.append({
                    "text": chunk,
                    "timings": relevant_timings,
                    "start_time": relevant_timings[0]["start"] if relevant_timings else 0,
                    "end_time": relevant_timings[-1]["start"] + relevant_timings[-1]["duration"] if relevant_timings else 0
                })
            
            # Extract just the text for embedding generation
            chunks = [c["text"] for c in chunks_with_metadata]
            
            # Generate embeddings for all chunks
            embeddings = get_embeddings(chunks)
            
            # Store in Supabase with 1 day expiry
            expiry_date = datetime.utcnow() + timedelta(days=1)
            
            # Prepare metadata for each chunk including timing information
            chunks_metadata = []
            for i, chunk_meta in enumerate(chunks_with_metadata):
                chunks_metadata.append({
                    "url": url,
                    "video_id": video_id,
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "start_time": chunk_meta["start_time"],
                    "end_time": chunk_meta["end_time"],
                    "timings": chunk_meta["timings"]
                })
            
            save_video_embeddings(
                video_id=video_id,
                chunks=chunks,
                embeddings=embeddings,
                expiry_date=expiry_date,
                chunks_metadata=chunks_metadata
            )
            
            # Mark as complete
            mark_video_complete(video_id)
            
            results.append({
                "video_id": video_id,
                "url": url,
                "status": "active",
                "chunks_count": len(chunks),
                "message": "Successfully processed"
            })
            
        except Exception as e:
            # Reset status on error so it can be retried
            if video_id:
                try:
                    supabase.table("video_status").delete().eq("video_id", video_id).execute()
                except:
                    pass  # Ignore cleanup errors
            
            results.append({
                "video_id": video_id,
                "url": url,
                "status": "error",
                "message": str(e)
            })
    
    return results
