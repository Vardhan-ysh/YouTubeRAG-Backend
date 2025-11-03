from app.utils.supabase_client import get_video_status, get_video_embeddings
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def generate_video_summary(video_id: str) -> dict:
    """
    Generate a markdown summary of a video using its transcript chunks.
    
    Returns:
        dict with keys: video_id, summary (markdown), sources, status, message
    """
    try:
        # Check video status
        status = get_video_status(video_id)
        
        if status is None:
            return {
                "video_id": video_id,
                "summary": "",
                "sources": [],
                "status": "not_found",
                "message": "Video not found. Please process the video first using the /video/process endpoint."
            }
        
        if status == "processing":
            return {
                "video_id": video_id,
                "summary": "",
                "sources": [],
                "status": "processing",
                "message": "Video is still being processed. Please try again in a moment."
            }
        
        # Get all video embeddings/chunks
        embeddings_data = get_video_embeddings(video_id)
        
        if not embeddings_data:
            return {
                "video_id": video_id,
                "summary": "",
                "sources": [],
                "status": "error",
                "message": "No transcript data found for this video."
            }
        
        # Combine all chunks to get the full transcript with timing annotations
        transcript_parts = []
        for chunk in embeddings_data:
            metadata = chunk.get("metadata", {})
            start_time = metadata.get("start_time", 0)
            end_time = metadata.get("end_time", 0)
            
            # Format timestamp
            start_min, start_sec = divmod(int(start_time), 60)
            end_min, end_sec = divmod(int(end_time), 60)
            
            transcript_parts.append(
                f"[Chunk {chunk['chunk_index']} - Timestamp {start_min:02d}:{start_sec:02d} to {end_min:02d}:{end_sec:02d}]:\n{chunk['chunk_text']}"
            )
        
        full_transcript = "\n\n".join(transcript_parts)
        
        # Create prompt for Gemini to generate summary
        prompt = f"""You are a helpful assistant that creates comprehensive video summaries in markdown format.

Based on the following video transcript (with timestamps), create a well-structured markdown summary that includes:

1. **Overview**: A brief 2-3 sentence overview of the video
2. **Key Topics**: Main topics covered (as bullet points)
3. **Detailed Summary**: A comprehensive summary broken into logical sections with headers
4. **Key Takeaways**: Important points or conclusions (as bullet points)

When referencing specific information, mention the chunk numbers to help with source attribution.

Transcript:
{full_transcript}

Please format your response in clean markdown with proper headers (##, ###), bullet points, and emphasis where appropriate. Make it informative and easy to scan."""
        
        # Generate summary using Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt
        )
        
        summary_markdown = response.text
        
        # Prepare sources with full metadata
        sources = []
        for chunk in embeddings_data:
            metadata = chunk.get("metadata", {})
            sources.append({
                "chunk_index": chunk["chunk_index"],
                "text": chunk["chunk_text"],
                "start_time": metadata.get("start_time", 0.0),
                "end_time": metadata.get("end_time", 0.0),
                "url": f"https://www.youtube.com/watch?v={video_id}&t={int(metadata.get('start_time', 0))}s",
                "video_id": video_id
            })
        
        return {
            "video_id": video_id,
            "summary": summary_markdown,
            "sources": sources,
            "status": "success",
            "message": None
        }
        
    except Exception as e:
        return {
            "video_id": video_id,
            "summary": "",
            "sources": [],
            "status": "error",
            "message": f"An error occurred while generating summary: {str(e)}"
        }
