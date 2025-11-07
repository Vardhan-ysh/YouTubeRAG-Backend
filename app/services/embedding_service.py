import os
import httpx
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
            
            # Fetch transcript using the RapidAPI youtube-transcriptor service
            # Configure RapidAPI credentials via environment variables
            # Read raw environment variables first (before any cleaning)
            rapidapi_key = os.getenv("RAPIDAPI_KEY")
            rapidapi_host = os.getenv("RAPIDAPI_HOST", "youtube-transcriptor.p.rapidapi.com")
            requested_lang = os.getenv("TRANSCRIPT_LANG", "en")

            # DEBUG: print raw env values (repr) and whether they contain control chars.
            # Do NOT print the actual API key value to avoid leaking secrets.
            try:
                raw_host = os.getenv("RAPIDAPI_HOST")
                raw_lang = os.getenv("TRANSCRIPT_LANG")
                raw_key = os.getenv("RAPIDAPI_KEY")
                has_host_ctrl = any(ord(ch) < 32 for ch in (raw_host or ""))
                has_lang_ctrl = any(ord(ch) < 32 for ch in (raw_lang or ""))
                has_key_ctrl = any(ord(ch) < 32 for ch in (raw_key or ""))
                print(f"DEBUG env RAPIDAPI_HOST repr={raw_host!r}, contains_control={has_host_ctrl}")
                print(f"DEBUG env TRANSCRIPT_LANG repr={raw_lang!r}, contains_control={has_lang_ctrl}")
                print(f"DEBUG RAPIDAPI_KEY contains_control={has_key_ctrl}")
            except Exception:
                # Don't let debug logging break prod flow
                pass


            # Sanitize environment inputs to remove non-printable/control characters (CR/LF)
            # that can appear when secrets are created on Windows or via some CI systems.
            def _clean_env_value(s: str) -> str:
                if s is None:
                    return ""
                # Remove common control characters explicitly and strip whitespace
                if isinstance(s, str):
                    s = s.replace("\r", "").replace("\n", "").replace("\t", "")
                    # Also remove any remaining non-printable chars
                    s = ''.join(ch for ch in s if ord(ch) >= 32 and ord(ch) <= 126)
                    return s.strip()
                return ""

            rapidapi_host = _clean_env_value(rapidapi_host) or "youtube-transcriptor.p.rapidapi.com"
            requested_lang = _clean_env_value(requested_lang) or "en"
            rapidapi_key = _clean_env_value(rapidapi_key)

            if not rapidapi_key:
                raise RuntimeError("RAPIDAPI_KEY is not set in environment")

            # Sanitize the key and header values too
            rapidapi_key = _clean_env_value(rapidapi_key)
            headers = {
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": rapidapi_host,
                "Accept": "application/json",
                "User-Agent": "YouTubeRAG/1.0"
            }

            # Use httpx params rather than manual query string assembly to avoid URL encoding issues.
            # Clean the video_id too (remove whitespace/control chars)
            video_id = ''.join(ch for ch in (video_id or "") if ch.isprintable()).strip()

            params = {
                "video_id": video_id,
                "lang": requested_lang
            }

            # Validate host doesn't contain control characters or spaces
            if not rapidapi_host or any(ord(ch) < 32 or ch.isspace() for ch in rapidapi_host):
                raise RuntimeError(f"Invalid RAPIDAPI_HOST after sanitization: {repr(rapidapi_host)}")

            # Use a short timeout to avoid hanging and capture response body on error for debugging
            # Build URL and make a final sanitation pass on the constructed URL to strip any
            # remaining non-printable characters that might still be present.
            url_api = f"https://{rapidapi_host}/transcript"
            # Ensure url_api contains only printable ASCII characters
            url_api = ''.join(ch for ch in url_api if ch.isprintable())
            # Final trim of whitespace/control chars
            url_api = url_api.strip()

            # DEBUG: show repr, length and any non-printable char info for troubleshooting
            try:
                print(f"DEBUG final url_api repr={url_api!r}")
                print(f"DEBUG url_api length={len(url_api)}")
                # If the string is long enough, show the ord value at position 43 to match the error
                if len(url_api) > 43:
                    print(f"DEBUG char at pos43: {repr(url_api[43])} ord={ord(url_api[43])}")
            except Exception:
                pass

            # Also sanitize header values (remove control chars)
            for hk, hv in list(headers.items()):
                if isinstance(hv, str):
                    headers[hk] = ''.join(ch for ch in hv if ch.isprintable())

            # Log the request details (sanitized) to help debug invalid URL errors in prod.
            print(f"RapidAPI request -> url_api={repr(url_api)}, params={params}, x-rapidapi-host={repr(headers.get('x-rapidapi-host'))}")

            with httpx.Client(timeout=30.0) as client:
                try:
                    resp = client.get(url_api, headers=headers, params=params)
                except httpx.InvalidURL as iu:
                    # Surface a clearer error including sanitized url_api and video_id (but do not print the key)
                    raise RuntimeError(f"Invalid RapidAPI URL (url_api={url_api!r}, video_id={video_id!r}): {iu}") from iu

                if resp.status_code != 200:
                    # Include response body to help diagnose 400/4xx issues (invalid video id, missing captions, bad key, etc.)
                    raise RuntimeError(f"RapidAPI error {resp.status_code}: {resp.text}")
                api_data = resp.json()

            # The API returns a list, usually with one entry containing transcription
            if not api_data or not isinstance(api_data, list) or len(api_data) == 0:
                raise RuntimeError("No transcript data returned from RapidAPI")

            transcript_obj = api_data[0]

            # Normalize fetched_transcript interface expected by the rest of the code
            # The RapidAPI response contains 'transcription' list with items having
            # 'subtitle' (text), 'start' and 'dur' (duration)
            class FetchedTranscript:
                pass

            fetched_transcript = FetchedTranscript()
            # Basic fields
            fetched_transcript.language = requested_lang
            fetched_transcript.language_code = requested_lang
            # RapidAPI doesn't expose is_generated; assume False
            fetched_transcript.is_generated = False
            fetched_transcript.availableLangs = transcript_obj.get("availableLangs", [])
            fetched_transcript.lengthInSeconds = transcript_obj.get("lengthInSeconds")
            # Provide a list of snippet-like objects to match previous structure
            raw_transcription = transcript_obj.get("transcription", [])
            # Convert to objects with attributes: text, start, duration
            fetched_transcript.snippets = []
            for t in raw_transcription:
                text = t.get("subtitle") or t.get("text") or ""
                start = float(t.get("start", 0))
                duration = float(t.get("dur", t.get("duration", 0)))
                # Create a simple object
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
