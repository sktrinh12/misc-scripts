from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from sentence_transformers import SentenceTransformer
from huggingface_hub import InferenceClient
import requests
import asyncio
import os

app = FastAPI()

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
client = chromadb.PersistentClient(path="./chroma")
collection = client.get_collection("workitems")
# ollama_base_url = "http://localhost:11434/api"
client = InferenceClient(
    provider="auto",
    api_key=os.environ["HF_TOKEN"],
)


class QueryRequest(BaseModel):
    text: str
    model: str


MAX_CHUNKS = 10  # limit to top N chunks (from chroma)
MAX_CHARS_PER_CONTEXT = 4000  # safe token approximation for prompt
MAX_LLM_INPUT_CHUNKS = 700


def get_context(query: str, n_results: int = MAX_CHUNKS):
    """
    Query Chroma for most relevant chunks.
    """
    query_embedding = embedding_model.encode([query]).tolist()[0]

    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)

    urls = []
    context_chunks = []
    for idx, (doc, meta, doc_id) in enumerate(
        zip(results["documents"][0], results["metadatas"][0], results["ids"][0])
    ):
        work_id = int(doc_id.split("_")[0])
        title = meta.get("title", "Untitled Work Item")

        truncated_doc = doc[:MAX_LLM_INPUT_CHUNKS]
        context_chunks.append(f"[WORK ITEM {work_id} | COMMENT {idx}] {truncated_doc}")
        url = f"https://dev.azure.com/preludetx/PreludeTx_Dotmatics_2024/_boards/board/t/PreludeTx_Dotmatics_2024%20Team/Stories?workitem={work_id}"
        urls.append({"id": work_id, "title": title, "url": url})

    seen = set()
    unique_urls = []
    for u in urls:
        if u["id"] not in seen:
            seen.add(u["id"])
            unique_urls.append(u)

    urls = sorted(unique_urls, key=lambda x: x["id"], reverse=True)
    full_context = "\n".join(context_chunks)
    if len(full_context) > MAX_CHARS_PER_CONTEXT:
        full_context = full_context[:MAX_CHARS_PER_CONTEXT] + "\n...[truncated]"

    return full_context, urls


#
# def get_ollama_models() -> list[str]:
#     ollama_url = f"{ollama_base_url}/tags"
#     try:
#         response = requests.get(ollama_url)
#         response.raise_for_status()
#         data = response.json()
#         return [m["name"] for m in data.get("models", [])]
#     except requests.exceptions.RequestException as e:
#         raise RuntimeError(f"Error fetching models from Ollama: {e}")


def ask_ollama(context: str, question: str, model: str):
    """
    Query Ollama model with structured prompt and chunked context.
    """
    prompt = f"""
You are an assistant for Azure DevOps work items.
Use the provided context to answer the question.
The context is formatted as [WORK ITEM NUMBER | COMMENT CHUNK INDEX].
- The work item number is the unique identifier of a User Story or Bug.
- The comment chunk index represents a 200-character chunk of a comment.
Only use the context provided. Do not invent information.
Keep answers concise and professional.

Context:
{context}

Question: {question}
Answer:
"""

    ollama_url = f"{ollama_base_url}/generate"
    payload = {"model": model, "prompt": prompt, "stream": False}
    try:
        response = requests.post(ollama_url, json=payload)
        # Raise an exception for HTTP status codes >= 400
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise HTTPException(
                status_code=400, detail=f"Ollama API returned error: {data['error']}"
            )

        return data.get("response", "No response from Ollama.")

    except requests.exceptions.HTTPError as e:
        # Specific HTTP errors from Ollama server
        raise HTTPException(
            status_code=response.status_code, detail=f"Ollama HTTP error: {e}"
        )
    except requests.exceptions.RequestException as e:
        # Network or connection errors
        raise HTTPException(status_code=500, detail=f"Error connecting to Ollama: {e}")


def ask_hf(context: str, question: str, model: str):
    """
    Query HuggingFace inference API model with structured prompt and chunked context.
    """
    messages = [
        {
            "role": "system",
            "content": """You are an assistant for Azure DevOps work items.
            Use the provided context to answer the question.
            The context is formatted as [WORK ITEM NUMBER | COMMENT CHUNK INDEX].
            - The work item number is the unique identifier of a User Story or Bug.
            - The comment chunk index represents a 200-character chunk of a comment.
            Only use the context provided. Do not invent information.
            Keep answers concise and professional.""",
        },
        {
            "role": "user",
            "content": f"""Context:
            {context}
            
            Question: {question}""",
        },
    ]

    completion = client.chat.completions.create(model=model, messages=messages)
    return completion


@app.post("/query")
def query_rag(request: QueryRequest):
    context, urls = get_context(request.text)

    if request.model:
        # answer = ask_ollama(context, request.text, request.model)
        answer = ask_hf(context, request.text, request.model)
    else:
        answer = "None"

    return {
        "answer": answer.choices[0].message.content,
        "context": context,
        "urls": urls,
    }


@app.post("/mock-query")
async def mock_query():
    await asyncio.sleep(4)
    return {
        "answer": f"This is a mock response",
        "context": "[WORK ITEM XXX | COMMENT XX ] Here is some mock context text to simulate embeddings or long content.",
        "urls": [
            {"id": 1, "title": "Example work item", "url": "https://example.com/item1"},
            {
                "id": 2,
                "title": "Another item with a longer title to test truncation in UI",
                "url": "https://example.com/item2",
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
