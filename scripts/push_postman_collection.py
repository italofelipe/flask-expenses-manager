#!/usr/bin/env python3
"""POSTMAN-04 — Push Postman collection to Postman Cloud via API.

Reads the generated collection JSON, computes its SHA-256 hash, and
pushes it to the Postman Cloud API only if the hash has changed since
the last push (idempotent).

Required environment variables:
    POSTMAN_API_KEY         — Postman API key (from GH secrets)
    POSTMAN_COLLECTION_ID   — Target collection UID in Postman Cloud
    POSTMAN_WORKSPACE_ID    — (optional) Workspace for logging

Usage:
    python3 scripts/push_postman_collection.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_PATH = ROOT / "api-tests" / "postman" / "auraxis.postman_collection.json"
HASH_CACHE_PATH = ROOT / ".postman-push-hash"

POSTMAN_API_BASE = "https://api.getpostman.com"


def _compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _postman_request(
    method: str, path: str, api_key: str, data: bytes | None = None
) -> dict:
    url = f"{POSTMAN_API_BASE}{path}"
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json",
    }
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Postman API error: HTTP {e.code} — {body}", file=sys.stderr)
        raise


def main() -> None:
    api_key = os.environ.get("POSTMAN_API_KEY", "")
    collection_id = os.environ.get("POSTMAN_COLLECTION_ID", "")

    if not api_key:
        print("POSTMAN_API_KEY not set — skipping Postman Cloud push.")
        sys.exit(0)

    if not collection_id:
        print("ERROR: POSTMAN_COLLECTION_ID is required.", file=sys.stderr)
        sys.exit(1)

    if not COLLECTION_PATH.exists():
        print(
            f"ERROR: {COLLECTION_PATH} not found. Run: npm run postman:build",
            file=sys.stderr,
        )
        sys.exit(1)

    content = COLLECTION_PATH.read_bytes()
    current_hash = _compute_hash(content)

    # Check cached hash for idempotency
    if HASH_CACHE_PATH.exists():
        cached_hash = HASH_CACHE_PATH.read_text().strip()
        if cached_hash == current_hash:
            print(f"Collection unchanged (hash={current_hash[:12]}…). Skipping push.")
            return

    collection = json.loads(content)

    # Get current version from Postman Cloud
    workspace_id = os.environ.get("POSTMAN_WORKSPACE_ID", "")
    print(f"Pushing collection to Postman Cloud (id={collection_id})...")
    if workspace_id:
        print(f"  Workspace: {workspace_id}")

    # PUT /collections/{collection_id}
    payload = json.dumps({"collection": collection}).encode("utf-8")
    result = _postman_request(
        "PUT", f"/collections/{collection_id}", api_key, data=payload
    )

    updated = result.get("collection", {})
    print(
        f"Push successful. "
        f"Collection: {updated.get('name', '?')} "
        f"(uid={updated.get('uid', '?')})"
    )

    # Cache the hash
    HASH_CACHE_PATH.write_text(current_hash + "\n")
    print(f"Hash cached: {current_hash[:12]}…")


if __name__ == "__main__":
    main()
