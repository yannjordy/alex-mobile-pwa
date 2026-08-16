import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://tdcgmkccdaaanmmaaqpw.supabase.co"
)
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")

_headers = {
    "apikey": SUPABASE_ANON_KEY or SUPABASE_SERVICE_KEY or "",
    "Content-Type": "application/json",
}
if SUPABASE_SERVICE_KEY:
    _headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_KEY}"
elif SUPABASE_ANON_KEY:
    _headers["Authorization"] = f"Bearer {SUPABASE_ANON_KEY}"


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


async def query(
    table: str,
    select: str = "*",
    filters: Optional[dict] = None,
    order: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    params: dict[str, Any] = {"select": select}
    if filters:
        params.update(filters)
    if order:
        params["order"] = order
    if limit:
        params["limit"] = limit

    async with httpx.AsyncClient() as client:
        r = await client.get(_url(table), headers=_headers, params=params)
        r.raise_for_status()
        return r.json()


async def insert(table: str, data: dict | list[dict]) -> list[dict]:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _url(table), headers=_headers, json=data if isinstance(data, list) else [data]
        )
        r.raise_for_status()
        return r.json()


async def update(
    table: str, data: dict, filters: dict
) -> list[dict]:
    headers = {**_headers, "Prefer": "return=representation"}
    async with httpx.AsyncClient() as client:
        r = await client.patch(_url(table), headers=headers, json=data, params=filters)
        r.raise_for_status()
        return r.json()


async def upsert(table: str, data: dict | list[dict]) -> list[dict]:
    headers = {**_headers, "Prefer": "return=representation,resolution=merge-duplicates"}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _url(table),
            headers=headers,
            json=data if isinstance(data, list) else [data],
        )
        r.raise_for_status()
        return r.json()


async def delete(table: str, filters: dict) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.delete(_url(table), headers=_headers, params=filters)
        r.raise_for_status()


async def save_conversation(role: str, content: str, source: Optional[str] = None, model: Optional[str] = None) -> dict:
    records = await insert("conversations", {
        "role": role,
        "content": content,
        "source": source,
        "model": model,
    })
    return records[0] if records else {}


async def get_recent_conversations(limit: int = 50) -> list[dict]:
    return await query(
        "conversations",
        order="created_at.desc",
        limit=limit,
    )


async def save_memory(key: str, value: str, category: str = "general") -> dict:
    records = await upsert("memories", {
        "key": key,
        "value": value,
        "category": category,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return records[0] if records else {}


async def get_memory(key: str) -> Optional[dict]:
    records = await query("memories", filters={"key": f"eq.{key}"})
    return records[0] if records else None


async def get_all_memories() -> list[dict]:
    return await query("memories", order="updated_at.desc")


async def save_setting(key: str, value: Any) -> dict:
    records = await upsert("settings", {
        "key": key,
        "value": value,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    return records[0] if records else {}


async def get_setting(key: str) -> Optional[Any]:
    records = await query("settings", filters={"key": f"eq.{key}"})
    return records[0].get("value") if records else None


async def add_knowledge(title: str, content: str, tags: Optional[list[str]] = None) -> dict:
    records = await insert("knowledge", {
        "title": title,
        "content": content,
        "tags": tags or [],
    })
    return records[0] if records else {}


async def search_knowledge(tags: Optional[list[str]] = None) -> list[dict]:
    return await query("knowledge", order="updated_at.desc")


async def log_tool(tool_name: str, params: Optional[dict] = None, result: Optional[str] = None, success: bool = True) -> dict:
    records = await insert("tool_logs", {
        "tool_name": tool_name,
        "params": params,
        "result": result,
        "success": success,
    })
    return records[0] if records else {}
