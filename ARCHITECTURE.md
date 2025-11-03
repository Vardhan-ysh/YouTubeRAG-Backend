# System Architecture Diagram

## Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLIENT (Frontend)                         │
└────────────────────┬────────────────────────────┬───────────────────┘
                     │                            │
                     │ POST /video/process        │ POST /chat/query
                     │ {"urls": [...]}            │ {"query": "...", 
                     │                            │  "video_id": "..."}
                     ↓                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────┐                    ┌──────────────────────┐  │
│  │  video_router     │                    │   chat_router        │  │
│  │  (video.py)       │                    │   (chat.py)          │  │
│  └─────────┬─────────┘                    └──────────┬───────────┘  │
│            │                                          │             │
│            ↓                                          ↓             │
│  ┌───────────────────┐                    ┌──────────────────────┐  │
│  │ embedding_service │                    │   chat_service       │  │
│  │ (embedding_       │                    │   (chat_service.py)  │  │
│  │  service.py)      │                    │                      │  │
│  │                   │                    │   • Check status     │  │
│  │ • Extract video   │                    │   • Generate query   │  │
│  │   ID              │                    │     embedding        │  │
│  │ • Fetch           │                    │   • Similarity       │  │
│  │   transcript      │                    │     search           │  │
│  │ • Chunk text      │                    │   • RAG with Gemini  │  │
│  │ • Generate        │                    │                      │  │
│  │   embeddings      │                    │                      │  │
│  │ • Store in DB     │                    │                      │  │
│  └─────────┬─────────┘                    └───────────┬──────────┘  │
│            │                                          │             │
│            └──────────┬───────────────────────────────┘             │
│                       │                                             │
│                       ↓                                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              UTILITY MODULES                                 │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │  embedding_client.py    │  supabase_client.py                │   │
│  │  • get_embeddings()     │  • get_video_status()              │   │
│  │  • Gemini API           │  • mark_video_processing()         │   │
│  │                         │  • mark_video_complete()           │   │
│  │                         │  • save_video_embeddings()         │   │
│  │                         │  • get_video_embeddings()          │   │
│  │                         │  • similarity_search()             │   │
│  └─────────────────────────┴────────────────────────────────────┘   │
│                                                                     │
└────────────────────┬────────────────────────────┬───────────────────┘
                     │                            │
                     ↓                            ↓
┌─────────────────────────────────┐  ┌──────────────────────────────┐
│       EXTERNAL APIS              │  │      SUPABASE DATABASE       │
├─────────────────────────────────┤  ├──────────────────────────────┤
│                                  │  │                              │
│  • YouTube Transcript API        │  │  ┌────────────────────────┐ │
│    - Fetch transcripts           │  │  │  video_status          │ │
│    - Support multiple languages  │  │  ├────────────────────────┤ │
│                                  │  │  │ • video_id (PK)        │ │
│  • Google Gemini AI              │  │  │ • status               │ │
│    - Embedding generation        │  │  │ • updated_at           │ │
│      (gemini-embedding-001)      │  │  │ • created_at           │ │
│    - Text generation             │  │  └────────────────────────┘ │
│      (gemini-2.0-flash-exp)      │  │                              │
│                                  │  │  ┌────────────────────────┐ │
└──────────────────────────────────┘  │  │  video_embeddings      │ │
                                      │  ├────────────────────────┤ │
                                      │  │ • id (PK)              │ │
                                      │  │ • video_id             │ │
                                      │  │ • chunk_index          │ │
                                      │  │ • chunk_text           │ │
                                      │  │ • embedding (vector)   │ │
                                      │  │ • expiry_date          │ │
                                      │  │ • metadata (jsonb)     │ │
                                      │  │ • created_at           │ │
                                      │  └────────────────────────┘ │
                                      └──────────────────────────────┘
```

## Data Flow Sequences

### 1. Video Processing Sequence

```
Client          API Route        Service              Utils                External         Database
  │                │                │                   │                     │                │
  │  POST /video   │                │                   │                     │                │
  │  /process      │                │                   │                     │                │
  ├───────────────>│                │                   │                     │                │
  │                │  process_      │                   │                     │                │
  │                │  videos()      │                   │                     │                │
  │                ├───────────────>│                   │                     │                │
  │                │                │  get_video_       │                     │                │
  │                │                │  status()         │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  SELECT * FROM      │                │
  │                │                │                   │  video_status       │                │
  │                │                │                   ├────────────────────>│                │
  │                │                │                   │<────────────────────┤                │
  │                │                │<──────────────────┤  status/null        │                │
  │                │                │                   │                     │                │
  │                │                │  mark_video_      │                     │                │
  │                │                │  processing()     │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  UPSERT status      │                │
  │                │                │                   ├────────────────────>│                │
  │                │                │                   │                     │                │
  │                │                │                   │     Fetch           │                │
  │                │                │                   │     Transcript      │                │
  │                │                ├──────────────────────────────────────>  │                │
  │                │                │<─────────────────────────────────────── │                │
  │                │                │     transcript data                     │                │
  │                │                │                   │                     │                │
  │                │                │  get_embeddings() │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  Generate           │                │
  │                │                │                   │  Embeddings         │                │
  │                │                │                   ├────────────────────────────────────> │
  │                │                │                   │<─────────────────────────────────── │
  │                │                │<──────────────────┤  embeddings[]       │                │
  │                │                │                   │                     │                │
  │                │                │  save_video_      │                     │                │
  │                │                │  embeddings()     │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  INSERT INTO        │                │
  │                │                │                   │  video_embeddings   │                │
  │                │                │                   ├────────────────────>│                │
  │                │                │                   │                     │                │
  │                │                │  mark_video_      │                     │                │
  │                │                │  complete()       │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  UPDATE status      │                │
  │                │                │                   ├────────────────────>│                │
  │                │<───────────────┤                   │                     │                │
  │                │  results[]     │                   │                     │                │
  │<───────────────┤                │                   │                     │                │
  │  response      │                │                   │                     │                │
```

### 2. Chat Query Sequence

```
Client          API Route        Service              Utils                External         Database
  │                │                │                   │                     │                │
  │  POST /chat    │                │                   │                     │                │
  │  /query        │                │                   │                     │                │
  ├───────────────>│                │                   │                     │                │
  │                │  handle_chat() │                   │                     │                │
  │                ├───────────────>│                   │                     │                │
  │                │                │  get_video_       │                     │                │
  │                │                │  status()         │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  SELECT status      │                │
  │                │                │                   ├────────────────────>│                │
  │                │                │                   │<────────────────────┤                │
  │                │                │<──────────────────┤  "active"           │                │
  │                │                │                   │                     │                │
  │                │                │  get_embeddings() │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  Generate Query     │                │
  │                │                │                   │  Embedding          │                │
  │                │                │                   ├────────────────────────────────────> │
  │                │                │                   │<─────────────────────────────────── │
  │                │                │<──────────────────┤  query_embedding    │                │
  │                │                │                   │                     │                │
  │                │                │  similarity_      │                     │                │
  │                │                │  search()         │                     │                │
  │                │                ├──────────────────>│                     │                │
  │                │                │                   │  get_video_         │                │
  │                │                │                   │  embeddings()       │                │
  │                │                │                   ├────────────────────>│                │
  │                │                │                   │<────────────────────┤                │
  │                │                │                   │  all embeddings     │                │
  │                │                │                   │  (cosine similarity)│                │
  │                │                │<──────────────────┤  top 5 chunks       │                │
  │                │                │                   │                     │                │
  │                │                │                   │     Generate        │                │
  │                │                │                   │     Answer          │                │
  │                │                ├──────────────────────────────────────>  │                │
  │                │                │<─────────────────────────────────────── │                │
  │                │                │     AI response                         │                │
  │                │<───────────────┤                   │                     │                │
  │                │  answer +      │                   │                     │                │
  │                │  sources       │                   │                     │                │
  │<───────────────┤                │                   │                     │                │
  │  response      │                │                   │                     │                │
```

## Technology Stack

```
┌────────────────────────────────────────────────────────────────┐
│                        TECHNOLOGY STACK                         │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Backend Framework:                                             │
│    • FastAPI (Python 3.12+)                                     │
│    • Pydantic for validation                                    │
│    • Uvicorn for ASGI server                                    │
│                                                                 │
│  AI/ML:                                                         │
│    • Google Gemini AI                                           │
│      - gemini-embedding-001 (embeddings)                        │
│      - gemini-2.0-flash-exp (text generation)                   │
│    • NumPy for vector operations                                │
│                                                                 │
│  Database:                                                      │
│    • Supabase (PostgreSQL)                                      │
│    • pgvector extension                                         │
│    • Row Level Security                                         │
│                                                                 │
│  External APIs:                                                 │
│    • youtube-transcript-api                                     │
│    • Google GenAI SDK                                           │
│                                                                 │
│  Development:                                                   │
│    • Poetry for dependency management                           │
│    • python-dotenv for configuration                            │
│    • httpx for async HTTP                                       │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

## Status State Machine

```
                    ┌─────────────┐
                    │  NOT FOUND  │
                    └──────┬──────┘
                           │
                           │ POST /video/process
                           │
                           ↓
                    ┌─────────────┐
                    │ PROCESSING  │◄───┐
                    └──────┬──────┘    │
                           │           │ Retry on
                           │           │ failure
                           │           │
              Success      │           │
                           ↓           │
                    ┌─────────────┐    │
                    │   ACTIVE    │    │
                    └──────┬──────┘    │
                           │           │
                           │           │
              Can answer   │           │
              queries      │           │
                           │           │
                           ↓           │
                    ┌─────────────┐    │
                    │  EXPIRED    │────┘
                    │ (1 day)     │
                    └─────────────┘
                           │
                           │ Cleanup job
                           ↓
                    ┌─────────────┐
                    │   DELETED   │
                    └─────────────┘
```

## Embedding Pipeline

```
┌──────────────────────────────────────────────────────────────────┐
│                      EMBEDDING PIPELINE                           │
└──────────────────────────────────────────────────────────────────┘

YouTube Transcript (Full Text)
         │
         │ 1. Fetch
         ↓
  "Hey there, welcome to..."
         │
         │ 2. Chunk (1000 chars, 200 overlap)
         ↓
┌────────────────────┬────────────────────┬────────────────────┐
│  Chunk 0           │  Chunk 1           │  Chunk 2           │
│  [0:1000]          │  [800:1800]        │  [1600:2600]       │
└─────────┬──────────┴─────────┬──────────┴─────────┬──────────┘
          │                    │                    │
          │ 3. Generate Embeddings (Gemini)
          ↓                    ↓                    ↓
    [0.123, 0.456,       [0.789, 0.234,       [0.567, 0.890,
     ..., 768 dims]       ..., 768 dims]       ..., 768 dims]
          │                    │                    │
          │ 4. Store with metadata
          ↓                    ↓                    ↓
┌─────────────────────────────────────────────────────────────┐
│                    SUPABASE DATABASE                         │
├──────────────┬──────────────┬──────────────┬────────────────┤
│ video_id     │ chunk_index  │ chunk_text   │ embedding      │
├──────────────┼──────────────┼──────────────┼────────────────┤
│ "abc123"     │ 0            │ "Hey there..." │ [0.123, ...]  │
│ "abc123"     │ 1            │ "...welcome..."│ [0.789, ...]  │
│ "abc123"     │ 2            │ "...to this..."│ [0.567, ...]  │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

## Query Processing

```
User Query: "What is the main topic?"
     │
     │ 1. Generate embedding
     ↓
[0.234, 0.567, ..., 768 dims]
     │
     │ 2. Compare with all stored embeddings
     │    (Cosine Similarity)
     ↓
┌────────────────────────────────────────┐
│  Chunk 5: similarity = 0.92            │  ◄── Most similar
│  Chunk 2: similarity = 0.87            │
│  Chunk 8: similarity = 0.84            │
│  Chunk 1: similarity = 0.79            │
│  Chunk 4: similarity = 0.75            │
└─────────────────┬──────────────────────┘
                  │
                  │ 3. Retrieve top 5 chunks
                  ↓
         Context Text (Combined)
                  │
                  │ 4. Build prompt
                  ↓
┌────────────────────────────────────────┐
│ Context: [chunks 5, 2, 8, 1, 4]        │
│ Question: "What is the main topic?"    │
└─────────────────┬──────────────────────┘
                  │
                  │ 5. Send to Gemini
                  ↓
    "The main topic discussed is..."
                  │
                  │ 6. Return with sources
                  ↓
┌────────────────────────────────────────┐
│ Answer: "The main topic..."            │
│ Sources: [chunk 5, chunk 2, ...]       │
│ Status: "success"                      │
└────────────────────────────────────────┘
```
