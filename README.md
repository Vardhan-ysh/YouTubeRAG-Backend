# YouTube RAG Backend

This is the backend service for a Retrieval-Augmented Generation (RAG) system specialized for YouTube videos. It allows users to query YouTube videos and receive direct, context-aware answers extracted from the video's spoken transcript.

## Overview and Features
- **YouTube Transcript Processing:** Extracts the full captions or transcripts of the video using an external API (`RapidAPI`).
- **Content Vectorization:** Breaks the text into small sequential chunks and uses Google Gemini (`gemini-embedding-001`) to generate vector embeddings.
- **Vector Storage:** Saves all embedded data securely in Supabase (PostgreSQL with `pgvector`) for highly efficient similarity retrieval.
- **RAG Implementation:** Given a user query (e.g., "What ingredients did the chef use?"), it searches the database for the most relevant transcript segments, passes them to a generative model (Gemini 2.0 Flash), and streams back accurate, conversational answers along with precise source chunks.

---

## Security and Vulnerability Analysis
A review of the application's architecture and configuration highlights the following considerations:

1. **CORS Configuration:** The current implementation in `app/main.py` explicitly allows traffic from any origin (`allow_origins=["*"]`). In production, this should be scoped strictly to the frontend URL to prevent cross-origin attacks.
2. **Dependency Management:** The core dependencies in `pyproject.toml` are currently secure. It is recommended to use `uv sync` regularly to keep standard packages up to date.
3. **Environment Security:** The codebase correctly utilizes `.env` files for configuration. In production environments, ensure that `SUPABASE_ANON_KEY`, `DATABASE_URL`, and all external API keys are heavily restricted and never committed to source control.
4. **Endpoint Security:** The core API endpoints (`/video/process` and `/chat/query`) currently do not enforce user authentication or rate limiting. Implement FastAPI `Depends` or appropriate middleware to limit requests and verify caller identity.

---

## Requirements and Setup

### Prerequisites
- Python 3.12 or newer
- A RapidAPI account (for YouTube transcript fetching)
- A Google Gemini API Key
- A Supabase account and an active project

### 1. Database Setup (Supabase)
Run the SQL script `supabase_schema.sql` found in the root directory within your Supabase SQL Editor. This script enables `pgvector`, creates the necessary `video_status` and `video_embeddings` tables, and sets up indexing for similarity searches.

### 2. Environment Variables
Copy the provided `.env.example` to a new file named `.env` and provide the required keys:

```env
# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# RapidAPI (video-transcript-scraper) configuration
RAPIDAPI_KEY=your_rapidapi_key_here
RAPIDAPI_HOST=video-transcript-scraper.p.rapidapi.com
TRANSCRIPT_LANG=en
```

### 3. Dependency Installation
This project leverages `uv` for lightning-fast dependency resolution. Run the following command in the project directory:

```bash
uv sync
```

---

## Usage

To run the FastAPI server in development mode, execute:

```bash
uv run uvicorn app.main:app --port 8000 --reload
```

The server will be available at `http://localhost:8000`. The interactive Swagger API Documentation can be accessed at `http://localhost:8000/docs`.

---

## Core API Routes

### 1. Health Check
- **`GET /`**
  - Simple health check endpoint to verify the backend is active and responding.

### 2. Video Processing
- **`POST /api/video/process`**
  - **Payload Requirement:** `{"urls": ["https://youtube.com/watch?v=..."]}`
  - **Description:** Kicks off the chunking and embedding generation sequence for novel YouTube URLs. Returns the status of the background process.

### 3. Chat and Generation
- **`POST /api/chat/query`**
  - **Payload Requirement:** `{"query": "User's specific question", "video_id": "youtube_video_id"}`
  - **Description:** Checks if the requested video has been processed. If yes, it runs a semantic search on the query to find similar transcript chunks and uses the LLM to generate an answer based purely on that retrieved context.
