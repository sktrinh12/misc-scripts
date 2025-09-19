import os
import requests
import json
from datetime import datetime

from typing import Iterable, List, Union
# from chromadb import Client
# from chromadb.utils import embedding_functions

ORG_NAME = "preludetx"
PROJECT_NAME = "PreludeTx_Dotmatics_2024"
API_BASE = f"https://dev.azure.com/{ORG_NAME}/{PROJECT_NAME}/_apis"
API_VERSION = "7.0"

PAT = os.getenv("AZURE_DEVOPS_PAT")
if not PAT:
    raise RuntimeError("Please set AZURE_DEVOPS_PAT in env")

SESSION = requests.Session()
SESSION.auth = ("", PAT)
SESSION.headers.update({"Content-Type": "application/json"})

MAX_IDS_PER_BATCH = 200 # approx. the max for azure api


def run_wiql(query: str) -> dict:
    url = f"{API_BASE}/wit/wiql?api-version={API_VERSION}"
    r = SESSION.post(url, json={"query": query})
    r.raise_for_status()
    return r.json()

def _ensure_id_list(ids_or_id: Union[int, str, Iterable[int]]) -> List[int]:
    if isinstance(ids_or_id, (int, str)):
        return [int(ids_or_id)]
    if hasattr(ids_or_id, "__iter__"):
        return [int(i) for i in ids_or_id]
    raise TypeError("ids_or_id must be int or iterable of ints")

def _chunks(lst: List[int], n: int):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def get_work_item_details(ids_or_id: Union[int, Iterable[int]]) -> List[dict]:
    """
    Returns a list of work item JSON blobs. Accepts a single id or a list.
    Will chunk large lists into batches (<= MAX_IDS_PER_BATCH).
    Expands 'relations'.
    """
    ids = _ensure_id_list(ids_or_id)
    all_values = []
    for chunk in _chunks(ids, MAX_IDS_PER_BATCH):
        params = {
            "ids": ",".join(map(str, chunk)),
            "$expand": "relations",
            "api-version": API_VERSION
        }
        url = f"{API_BASE}/wit/workitems"
        r = SESSION.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        all_values.extend(data.get("value", []))
    return all_values

def get_comments(item_id: int) -> list:
    """
    Fetches all comments for a work item using the comments API (requires preview API version).
    Uses continuationToken from the response body to page through results.
    """
    url = f"{API_BASE}/wit/workItems/{item_id}/comments"
    params = {
        "api-version": "7.1-preview.4",   # required for the comments endpoint
        "$top": 100                       # page size
    }
    all_comments = []
    while True:
        r = SESSION.get(url, params=params)
        try:
            r.raise_for_status()
        except requests.HTTPError:
            raise RuntimeError(f"Failed to fetch comments for {item_id}: {r.status_code} {r.text}")

        data = r.json()
        all_comments.extend(data.get("comments", []))

        # Azure DevOps returns continuationToken in the response body (and sometimes nextPage)
        token = data.get("continuationToken")
        if token:
            params["continuationToken"] = token
            # loop and fetch next page
        else:
            break

    return all_comments

def fetch_linked_commit_if_any(rel_url: str) -> dict:
    """
    If a relation URL looks like a Git commit artifact, fetch it.
    This is heuristic: many relation URLs for commits include '/_apis/git/repositories/' and '/commits/'.
    """
    if "/_apis/git/repositories/" in rel_url and "/commits/" in rel_url:
        # ensure api-version param
        r = SESSION.get(rel_url, params={"api-version": API_VERSION})
        if r.ok:
            return r.json()
    return {}

if __name__ == "__main__":
    WIQL = """
    SELECT [System.Id], [System.Title]
    FROM WorkItems
    WHERE [System.TeamProject] = 'PreludeTx_Dotmatics_2024'
    ORDER BY [System.ChangedDate] DESC
    """
    wiql_res = run_wiql(WIQL)
    ids = [w["id"] for w in wiql_res.get("workItems", [])]
    print(f"Found {len(ids)} work items")

    work_items = get_work_item_details(ids)

    # assemble a flat JSON record for each item (and optionally fetch comments/commit details)
    records = []
    for wi in work_items:
        item_id = wi["id"]
        fields = wi.get("fields", {})
        relations = wi.get("relations", [])
        # classify relations heuristically
        parents, children, commits, other_rels = [], [], [], []
        for r in relations:
            attrs = r.get("attributes", {}) or {}
            name = (attrs.get("name") or "").lower()
            url = r.get("url")
            if "parent" in name:
                parents.append(url)
            elif "child" in name:
                children.append(url)
            elif url and ("/_apis/git/repositories/" in url and "/commits/" in url or "commit" in name or "fixed in" in name.lower()):
                commits.append(url)
            else:
                other_rels.append({"rel": r.get("rel"), "url": url, "attributes": attrs})

        # fetch comment texts
        comments = get_comments(item_id)
        # optionally fetch commit details
        commit_details = [fetch_linked_commit_if_any(curl) for curl in commits]

        record = {
            "id": item_id,
            "title": fields.get("System.Title"),
            "description": fields.get("System.Description", ""),
            "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
            "tags": fields.get("System.Tags", ""),
            "story_points": fields.get("Microsoft.VSTS.Scheduling.StoryPoints", None),
            "type": fields.get("System.WorkItemType"),
            "state": fields.get("System.State"),
            "assignedTo": (fields.get("System.AssignedTo") or {}).get("displayName"),
            "createdDate": fields.get("System.CreatedDate"),
            "changedDate": fields.get("System.ChangedDate"),
            "parents": parents,
            "children": children,
            "commit_links": commits,
            "commit_details": commit_details,
            "comments": comments,
            "raw": wi
        }
        records.append(record)

    # save records locally as JSON
    with open("workitems_full.json", "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)

    print(f"Saved {len(records)} records to workitems_full.json")
