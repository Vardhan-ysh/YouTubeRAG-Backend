import os
import httpx
import urllib.parse
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
    # Remove all whitespace and non-printable characters (including \r, \n, \t, etc.)
    url = ''.join(char for char in url if char.isprintable() and not char.isspace())
    
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # If no pattern matches, assume the input is already a video ID
    # Should already be clean from above processing
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
            
            # Fetch transcript using the RapidAPI video-transcript-scraper service (POST JSON)
            # Configure RapidAPI credentials via environment variables
            # Read raw environment variables first (before any cleaning)
            rapidapi_key = os.getenv("RAPIDAPI_KEY")
            rapidapi_host = os.getenv("RAPIDAPI_HOST", "video-transcript-scraper.p.rapidapi.com")
            requested_lang = os.getenv("TRANSCRIPT_LANG", "en")

            # basic environment sanitization helper
            def _clean_env_value(s: str) -> str:
                if s is None:
                    return ""
                if isinstance(s, str):
                    s = s.replace("\r", "").replace("\n", "").replace("\t", "")
                    s = ''.join(ch for ch in s if 32 <= ord(ch) <= 126)
                    return s.strip()
                return ""

            rapidapi_host = _clean_env_value(rapidapi_host) or "video-transcript-scraper.p.rapidapi.com"
            # Normalize host: if someone supplied a full URL or a path, extract hostname only
            try:
                parsed = urllib.parse.urlparse(rapidapi_host)
                if parsed.netloc:
                    rapidapi_host = parsed.netloc
                else:
                    # strip any path segments if present
                    rapidapi_host = rapidapi_host.split('/')[0]
                rapidapi_host = rapidapi_host.strip()
            except Exception:
                # fallback to original cleaned value
                rapidapi_host = rapidapi_host
            requested_lang = _clean_env_value(requested_lang) or "en"
            rapidapi_key = _clean_env_value(rapidapi_key)

            if not rapidapi_key:
                raise RuntimeError("RAPIDAPI_KEY is not set in environment")

            headers = {
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": rapidapi_host,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "YouTubeRAG/1.0"
            }

            # Build the POST payload: the new API expects the full video URL
            clean_video_id = ''.join(ch for ch in (video_id or "") if ch.isprintable()).strip()

            # If the extracted value already looks like a URL, use it directly.
            # Otherwise build a standard YouTube watch URL from the video id.
            if clean_video_id.startswith("http://") or clean_video_id.startswith("https://"):
                video_url = clean_video_id
            elif clean_video_id.startswith("www.") or "youtube.com" in clean_video_id or "youtu.be" in clean_video_id:
                # ensure scheme exists
                video_url = clean_video_id if clean_video_id.startswith("http") else f"https://{clean_video_id}"
            else:
                video_url = f"https://www.youtube.com/watch?v={clean_video_id}"

            payload = {"video_url": video_url}

            # Validate host doesn't contain control characters or spaces
            if not rapidapi_host or any(ord(ch) < 32 or ch.isspace() for ch in rapidapi_host):
                raise RuntimeError(f"Invalid RAPIDAPI_HOST after sanitization: {repr(rapidapi_host)}")

            url_api = f"https://{rapidapi_host}/transcript"
            url_api = ''.join(ch for ch in url_api if ch.isprintable()).strip()

            print(f"RapidAPI POST -> url_api={repr(url_api)}, payload video_url={repr(video_url)}, x-rapidapi-host={repr(headers.get('x-rapidapi-host'))}")

            with httpx.Client(timeout=30.0) as client:
                try:
                    resp = client.post(url_api, headers=headers, json=payload)
                except httpx.InvalidURL as iu:
                    raise RuntimeError(f"Invalid RapidAPI URL (url_api={url_api!r}, video_url={video_url!r}): {iu}") from iu

                if resp.status_code != 200:
                    raise RuntimeError(f"RapidAPI error {resp.status_code}: {resp.text}")

                api_json = resp.json()

            # The new API responds with a JSON object containing status and data
            if not api_json or not isinstance(api_json, dict) or api_json.get("status") != "success":
                raise RuntimeError(f"No transcript data returned from RapidAPI or status != success: {api_json}")

            data_obj = api_json.get("data", {})

            # Normalize fetched_transcript to previous interface expected by the rest of the code
            class FetchedTranscript:
                pass

            fetched_transcript = FetchedTranscript()
            fetched_transcript.language = requested_lang
            fetched_transcript.language_code = requested_lang
            fetched_transcript.is_generated = False

            # video_info mappings (if present)
            video_info = data_obj.get("video_info", {}) or {}
            fetched_transcript.availableLangs = video_info.get("available_languages", [])
            fetched_transcript.lengthInSeconds = video_info.get("duration")

            # The new API returns transcript as a list of {text, start, end}
            raw_transcription = data_obj.get("transcript", []) or []
            fetched_transcript.snippets = []
            for t in raw_transcription:
                text = t.get("text") or ""
                start = float(t.get("start", 0.0))
                end = float(t.get("end", start))
                duration = max(0.0, end - start)
                class Snip:
                    pass
                s = Snip()
                s.text = text
                s.start = start
                s.duration = duration
                fetched_transcript.snippets.append(s)
            
            # Build text with timing information
            # Create a mapping of character position to timing info
            full_text = ""
            timing_map = []  # List of (start_pos, end_pos, start_time, duration)
            
            # Build timing map from RapidAPI-style snippets
            for snippet in fetched_transcript.snippets:
                start_pos = len(full_text)
                full_text += (snippet.text or "") + " "
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
            
            # Store in Supabase with 1 year expiry
            expiry_date = datetime.utcnow() + timedelta(days=365)
            
            # Prepare metadata for each chunk including timing information
            chunks_metadata = []
            for i, chunk_meta in enumerate(chunks_with_metadata):
                chunks_metadata.append({
                    "url": url,
                    "video_id": video_id,
                    "language": getattr(fetched_transcript, "language", requested_lang),
                    "language_code": getattr(fetched_transcript, "language_code", requested_lang),
                    "is_generated": getattr(fetched_transcript, "is_generated", False),
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
            
            import traceback
            error_details = f"{type(e).__name__}: {str(e)}"
            print(f"Error processing video {video_id}: {error_details}")
            print(traceback.format_exc())
            
            results.append({
                "video_id": video_id,
                "url": url,
                "status": "error",
                "message": error_details
            })
    
    return results
