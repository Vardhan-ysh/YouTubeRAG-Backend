from supabase import create_client
import os
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
import ast

load_dotenv()


# Helper to clean env values (remove CR/LF, tabs and other non-printable chars)
def _clean_env_value(s: str) -> str:
    if not s:
        return ""
    if not isinstance(s, str):
        s = str(s)
    # remove common control characters and any non-printable ASCII
    s = s.replace("\r", "").replace("\n", "").replace("\t", "")
    s = ''.join(ch for ch in s if 32 <= ord(ch) <= 126)
    return s.strip()

# Load and sanitize environment variables
SUPABASE_URL = _clean_env_value(os.getenv("SUPABASE_URL", ""))
SUPABASE_KEY = _clean_env_value(os.getenv("SUPABASE_ANON_KEY", ""))
DATABASE_URL = _clean_env_value(os.getenv("DATABASE_URL", ""))

# Lazily initialize the Supabase client so import-time errors don't crash the container
_supabase = None

def get_supabase():
    """Return a singleton Supabase client. Initialize on first call with sanitized env vars."""
    global _supabase
    if _supabase is not None:
        return _supabase

    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is not set or empty")
    if not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_ANON_KEY is not set or empty")

    # Basic validation of URL format
    if not SUPABASE_URL.startswith("http://") and not SUPABASE_URL.startswith("https://"):
        raise RuntimeError(f"Invalid SUPABASE_URL: {repr(SUPABASE_URL)}")

    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase

# Table names
VIDEO_STATUS_TABLE = "video_status"
VIDEO_EMBEDDINGS_TABLE = "video_embeddings"


def get_video_status(video_id: str) -> str | None:
    """
    Check the status of a video
    Returns: 'processing', 'active', or None if not found
    """
    try:
        sb = get_supabase()
        result = sb.table(VIDEO_STATUS_TABLE).select("status").eq("video_id", video_id).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]["status"]
        return None
    except Exception as e:
        print(f"Error checking video status: {e}")
        return None


def mark_video_processing(video_id: str):
    """Mark video as processing"""
    try:
        sb = get_supabase()
        sb.table(VIDEO_STATUS_TABLE).upsert({
            "video_id": video_id,
            "status": "processing",
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error marking video as processing: {e}")
        raise


def mark_video_complete(video_id: str):
    """Mark video as active/complete"""
    try:
        sb = get_supabase()
        sb.table(VIDEO_STATUS_TABLE).upsert({
            "video_id": video_id,
            "status": "active",
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Error marking video as complete: {e}")
        raise


def save_video_embeddings(
    video_id: str,
    chunks: list[str],
    embeddings: list[np.ndarray],
    expiry_date: datetime,
    chunks_metadata: list[dict] = None
):
    """
    Save video chunks and their embeddings to Supabase
    chunks_metadata: list of metadata dicts, one per chunk
    """
    try:
        records = []
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Use per-chunk metadata if provided, otherwise use empty dict
            chunk_meta = chunks_metadata[idx] if chunks_metadata and idx < len(chunks_metadata) else {}
            
            records.append({
                "video_id": video_id,
                "chunk_index": idx,
                "chunk_text": chunk,
                "embedding": embedding.tolist(),  # Convert numpy array to list
                "expiry_date": expiry_date.isoformat(),
                "metadata": chunk_meta,
                "created_at": datetime.utcnow().isoformat()
            })
        
        # Insert all records
        sb = get_supabase()
        sb.table(VIDEO_EMBEDDINGS_TABLE).insert(records).execute()
        
    except Exception as e:
        print(f"Error saving embeddings: {e}")
        raise


def get_video_embeddings(video_id: str) -> list[dict] | None:
    """
    Retrieve all embeddings for a video including metadata
    Returns list of dicts with chunk_text, embedding, and metadata
    """
    try:
        sb = get_supabase()
        result = sb.table(VIDEO_EMBEDDINGS_TABLE)\
            .select("chunk_index, chunk_text, embedding, metadata")\
            .eq("video_id", video_id)\
            .gt("expiry_date", datetime.utcnow().isoformat())\
            .order("chunk_index")\
            .execute()

        if result.data:
            return result.data
        return None
    except Exception as e:
        print(f"Error retrieving embeddings: {e}")
        return None


import numpy as np
import ast

def similarity_search(video_id: str, query_embedding: np.ndarray, top_k: int = 5) -> list[dict]:
    """
    Perform similarity search using cosine similarity
    Returns top_k most similar chunks
    """
    try:
        print(f"Starting similarity search for video_id: {video_id}")
        
        # Get all embeddings for the video
        embeddings_data = get_video_embeddings(video_id)
        print(f"Retrieved {len(embeddings_data)} embeddings")
        
        if not embeddings_data:
            print("No embeddings found, returning empty list")
            return []
        
        results = []
        query_norm = np.linalg.norm(query_embedding)
        print(f"Query embedding norm: {query_norm}")
        
        if query_norm == 0:
            print("Query embedding norm is zero, returning empty list")
            return []
        
        for idx, item in enumerate(embeddings_data):
            # Convert string representation of embedding to numpy array
            embedding = np.array(ast.literal_eval(item["embedding"]))
            embedding_norm = np.linalg.norm(embedding)
            
            if embedding_norm == 0:
                print(f"Skipping chunk_index {item['chunk_index']} due to zero norm embedding")
                continue
            
            similarity = np.dot(query_embedding, embedding) / (query_norm * embedding_norm)
            
            print(f"Chunk {idx} - chunk_index: {item['chunk_index']}, similarity: {similarity}")
            
            results.append({
                "chunk_text": item["chunk_text"],
                "chunk_index": item["chunk_index"],
                "similarity": float(similarity),
                "metadata": item.get("metadata", {})  # Include metadata with timing info
            })
        
        print(f"Calculated similarity scores for {len(results)} chunks")
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        print(f"Returning top {top_k} results")
        
        return results[:top_k]
        
    except Exception as e:
        print(f"Error in similarity search: {e}")
        return []


def cleanup_expired_embeddings():
    """
    Delete expired embeddings (can be run as a cron job)
    """
    try:
        # First, get expired videos before deleting
        sb = get_supabase()
        expired_videos = sb.table(VIDEO_EMBEDDINGS_TABLE)\
            .select("video_id")\
            .lt("expiry_date", datetime.utcnow().isoformat())\
            .execute()
        
        # Delete expired embeddings
        sb.table(VIDEO_EMBEDDINGS_TABLE)\
            .delete()\
            .lt("expiry_date", datetime.utcnow().isoformat())\
            .execute()
        
        # Delete video status for expired videos
        if expired_videos.data:
            video_ids = list(set([v["video_id"] for v in expired_videos.data]))
            for vid in video_ids:
                sb.table(VIDEO_STATUS_TABLE).delete().eq("video_id", vid).execute()
                
    except Exception as e:
        print(f"Error cleaning up expired embeddings: {e}")
