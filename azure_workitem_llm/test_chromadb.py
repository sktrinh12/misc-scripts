import chromadb
from chromadb.utils import embedding_functions

# === Test query ===
# query = "how to use Prism in linux"
query = "how to map payload to target within the adc batch in dotmatics?"

# query = "what is feasability of payload relationship with target"
client = chromadb.PersistentClient(path="./chroma")
embedding_func = embedding_functions.DefaultEmbeddingFunction()
collection = client.get_collection("workitems")

results = collection.query(
    query_texts=[query],
    n_results=10,  # top relevant
)

print("\n=== Query Results ===")
for doc, meta, doc_id in zip(
    results["documents"][0],
    results["metadatas"][0],
    results["ids"][0]
):
    print(f"- ID: {doc_id}")
    print(f"  Metadata: {meta}")
    print(f"  Snippet: {doc[:200]}...\n")
