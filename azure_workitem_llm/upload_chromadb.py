import json
import chromadb
from chromadb.utils import embedding_functions

INPUT_FILE = "workitems_cleaned.json"

def load_cleaned_data(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    # Initialize Chroma client (in-memory)
    # client = chromadb.Client()
    # Initialize Chroma client (persistent)
    client = chromadb.PersistentClient(path="./chroma")

    # Pick a default embedding function (OpenAI, HuggingFace, etc.)
    # Here we’ll use the default all-MiniLM-L6-v2 HuggingFace model
    embedding_func = embedding_functions.DefaultEmbeddingFunction()

    collection = client.create_collection(
        name="workitems",
        embedding_function=embedding_func
    )

    records = load_cleaned_data(INPUT_FILE)

    # Upload documents into Chroma
    for rec in records:
        collection.add(
            documents=[rec["embedding_text"]],
            metadatas=[rec["metadata"]],
            ids=[f"{rec['id']}_{rec['chunk_index']}"]
        )

    print(f"Uploaded {len(records)} records into Chroma collection 'workitems'.")


if __name__ == "__main__":
    main()
