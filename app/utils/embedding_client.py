from google import genai
from google.genai import types
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def get_embeddings(texts: list[str]):
    """
    Generates embeddings for a list of texts using Gemini Embedding API.
    Returns a list of numpy arrays.
    """
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=texts,
        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT")
    )
    return [np.array(e.values) for e in response.embeddings]
