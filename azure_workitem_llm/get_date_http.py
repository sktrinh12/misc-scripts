import chromadb
from datetime import datetime, timezone
from chromadb.config import Settings
import os
import pprint

CHROMA_TOKEN = os.getenv('CHROMA_TOKEN')

def parse_mixed_date(value: str):
    """
    Parse various timestamp formats found in the metadata.
    Returns a UTC-aware datetime or None.
    """
    if not value:
        return None

    value = value.strip()

    # Try ISO 8601
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Already offset-aware
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # Try "January 28, 2025 at 20:08 UTC" or similar
    try:
        # Remove comma, "at", and "UTC"
        cleaned = value.replace(",", "").replace(" at ", " ").replace(" UTC", "")
        dt = datetime.strptime(cleaned, "%B %d %Y %H:%M")
        # Make it UTC-aware
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    # If all parsing fails
    return None

# client = chromadb.HttpClient(
#     host="https://chroma-ado.duckdns.org",
#     headers={"Authorization": f"Bearer {CHROMA_TOKEN}"},
#     port=443,
#     ssl=True,
# )

settings = Settings(anonymized_telemetry=False)
client = chromadb.PersistentClient(
    # path="/home/spencer-trinh/Documents/scripts/azure_workitem_llm/chroma",
    path="/home/spencer-trinh/Documents/rch-preludetx/scripts/ado-upd-embed/chroma_test",
    settings=settings
)

print(f"heartbeat: {client.heartbeat()}")
collection = client.get_collection("workitems")

total_count = collection.count()
print(f"total count of collection: {total_count}")
results = collection.get(include=["metadatas"])

offset = 0
limit = 200
latest_metadata = None
latest = None
record = collection.get(ids=["388_c0_0"], include=["metadatas"])
print(record["metadatas"])

# while True:

#     results = collection.get(include=["metadatas"], offset=offset, limit=limit)
#     metadatas = results.get("metadatas", [])
#     if not metadatas:
#         break
#
#     for metadata in metadatas:
#         if not metadata:
#             continue
#         for key in ("changedDate", "modifiedDate", "createdDate"):
#             value = metadata.get(key)
#             if value:
#                 dt = parse_mixed_date(value)
#                 if dt and (latest is None or dt > latest):
#                     latest = dt
#                     latest_metadata = metadata
#     for metadata in metadatas:
#         if any(metadata.get(k) for k in ("changedDate", "modifiedDate", "createdDate")):
#             print(
#                 f"[DEBUG] {metadata.get('title')}:",
#                 [metadata.get(k) for k in ("changedDate", "modifiedDate", "createdDate")]
#             )
#
#     offset += limit
#     if offset >= total_count:
#         break
#
# if latest and latest_metadata:
#     iso_str = latest.date().isoformat()
#     print(f"\n🕒 Latest date: {iso_str}")
#     print(f"📄 Latest title: {latest_metadata.get('title')}")
#     print("\n🔎 Full metadata:")
#     pprint.pprint(latest_metadata)
#
# else:
#     print("⚠️ No valid dates found.")
