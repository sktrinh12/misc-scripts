import chromadb

# client = chromadb.PersistentClient(path="./chroma_data")
# print("Listing collections...")
# print(client.list_collections())

client = chromadb.HttpClient(host="http://localhost:8000")
collection = client.get_collection("workitems")  # Ensure the collection exists

# Run a test query
results = collection.query(
    query_texts=["test query"],
    n_results=5
)
print(results)
