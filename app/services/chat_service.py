from app.utils.embedding_client import get_embeddings
from app.utils.supabase_client import get_video_status, similarity_search
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def handle_chat(video_id: str, question: str, session_id: str = None):
    """
    Handle chat queries using RAG:
    1. Check video status
    2. Generate embedding for query
    3. Perform similarity search
    4. Generate answer using Gemini with context
    """
    try:
        # Check video status
        status = get_video_status(video_id)
        
        if status is None:
            return {
                "answer": "Video not found. Please process the video first.",
                "sources": [],
                "status": "not_found"
            }
        
        if status == "processing":
            return {
                "answer": "Video is still being processed. Please try again in a moment.",
                "sources": [],
                "status": "processing"
            }
        
        # Generate embedding for the query
        query_embeddings = get_embeddings([question])
        query_embedding = query_embeddings[0]
        
        # Perform similarity search
        similar_chunks = similarity_search(video_id, query_embedding, top_k=5)
        
        if not similar_chunks:
            return {
                "answer": "No relevant information found in the video.",
                "sources": [],
                "status": "no_results"
            }
        
        # Prepare context from similar chunks with timing info
        context_parts = []
        for chunk in similar_chunks:
            metadata = chunk.get("metadata", {})
            start_time = metadata.get("start_time", 0)
            end_time = metadata.get("end_time", 0)
            
            # Format timestamp (convert seconds to mm:ss)
            start_min, start_sec = divmod(int(start_time), 60)
            end_min, end_sec = divmod(int(end_time), 60)
            
            context_parts.append(
                f"[Chunk {chunk['chunk_index']} - Timestamp {start_min:02d}:{start_sec:02d} to {end_min:02d}:{end_sec:02d}]:\n{chunk['chunk_text']}"
            )
        
        context = "\n\n".join(context_parts)
        
        # Create prompt for Gemini
        prompt = f"""You are a helpful assistant answering questions about a YouTube video based on its transcript.

Context from the video transcript (with timestamps):
{context}

User Question: {question}

Please provide a comprehensive answer based on the context above. If the context doesn't contain enough information to fully answer the question, acknowledge that and provide what information is available. When citing information, mention both the chunk numbers and timestamps."""
        
        # Generate response using Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        
        answer = response.text
        
        # Prepare sources with full metadata
        sources = []
        for chunk in similar_chunks:
            metadata = chunk.get("metadata", {})
            sources.append({
                "chunk_index": chunk["chunk_index"],
                "text": chunk["chunk_text"][:200] + "..." if len(chunk["chunk_text"]) > 200 else chunk["chunk_text"],
                "similarity": chunk["similarity"],
                "start_time": metadata.get("start_time", 0),
                "end_time": metadata.get("end_time", 0),
                "url": metadata.get("url", ""),
                "video_id": metadata.get("video_id", video_id)
            })
        
        
        return {
            "answer": answer,
            "sources": sources,
            "status": "success",
            "video_id": video_id
        }
        
    except Exception as e:
        return {
            "answer": f"An error occurred: {str(e)}",
            "sources": [],
            "status": "error"
        }
