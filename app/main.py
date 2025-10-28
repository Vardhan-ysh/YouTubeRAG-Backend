from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.router import router

app = FastAPI(title="YouTube RAG API")

# CORS (allow frontend requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router inclusion
app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {"message": "YouTube RAG backend is running 🚀"}
