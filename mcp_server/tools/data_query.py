"""数据网关工具：受授权保护的对外部系统的公共查询。

授权模型：
- 管理后台签发公共 Key（pk_...），并绑定该 Key 可访问的数据源
- HTTP 连接的客户端通过 Authorization: Bearer <key> 请求头携带密钥
- stdio 本地客户端可通过工具参数 api_key 兜底
- 若服务器尚未配置任何密钥，则处于"开放模式"（便于本地调试），并在结果中提示
"""

from __future__ import annotations

import json
import sqlite3
from urllib.parse import quote
from typing import Any

import httpx
from mcp.server.fastmcp import Context

from ..admin.storage import get_store

_MAX_ROWS = 500


def _bearer_from_ctx(ctx: Context) -> str | None:
    try:
        req = ctx.request_context.request  # HTTP 传输时为 Starlette Request
        if req is not None:
            auth = req.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                return auth[7:].strip()
    except Exception:  # stdio 传输没有 request
        pass
    return None


def _check_auth(ctx: Context, api_key_arg: str, source_id: str) -> str | None:
    """返回 None 表示通过，否则返回拒绝原因文本。"""
    store = get_store()
    keys = store.list_keys()
    if not keys:
        return None  # 开放模式：尚未配置任何密钥

    record = store.verify_key(api_key_arg or _bearer_from_ctx(ctx) or "")
    if record is None:
        return "拒绝访问：请携带有效的公共 Key（Authorization: Bearer pk_... 或 api_key 参数）"
    allowed = record.get("allowed_sources") or []
    if "*" not in allowed and source_id not in allowed:
        return f"拒绝访问：当前密钥无权访问数据源 '{source_id}'（已授权: {allowed or '无'}）"
    return None


def _coerce_params(source: dict, params: dict) -> dict:
    """按白名单校验并补全参数，防止注入任意参数。"""
    allowed: dict[str, str] = source.get("allowed_params") or {}
    defaults: dict[str, Any] = source.get("default_params") or {}
    merged = dict(defaults)
    merged.update(params or {})
    out = {}
    for name, value in merged.items():
        if name not in allowed:
            raise ValueError(f"参数 '{name}' 不在白名单中，允许的参数: {list(allowed)}")
        ptype = allowed[name]
        try:
            if ptype == "int":
                out[name] = int(value)
            elif ptype == "float":
                out[name] = float(value)
            else:
                out[name] = str(value)
        except (TypeError, ValueError):
            raise ValueError(f"参数 '{name}' 需要 {ptype} 类型，收到: {value!r}")
    return out


def _apply_filters(rows: list[dict], filters: dict) -> list[dict]:
    if not filters:
        return rows
    return [
        r for r in rows
        if all(str(r.get(k)) == str(v) for k, v in filters.items())
    ]


def _query_sqlite(source: dict, params: dict) -> list[dict]:
    conn = sqlite3.connect(source["dsn"])
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(source["query_template"], params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchmany(_MAX_ROWS + 1)]
    finally:
        conn.close()


async def _query_http(source: dict, params: dict) -> list[dict]:
    url = source["dsn"] + source["query_template"]
    for name, value in params.items():
        url = url.replace("{" + name + "}", quote(str(value), safe=""))
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers=source.get("headers") or {})
        resp.raise_for_status()
        try:
            payload = resp.json()
        except json.JSONDecodeError:
            return [{"text": resp.text[:5000]}]
    if isinstance(payload, list):
        return payload
    for key in ("data", "results", "items", "rows", "list"):
        if isinstance(payload, dict) and isinstance(payload.get(key), list):
            return payload[key]
    return [payload]


def register(mcp) -> None:
    @mcp.tool()
    async def list_data_sources(ctx: Context) -> str:
        """列出服务器上可用的数据源及其参数说明（不包含敏感连接信息）。"""
        store = get_store()
        sources = [
            {
                "id": s["id"],
                "name": s.get("name", ""),
                "type": s["type"],
                "description": s.get("description", ""),
                "allowed_params": s.get("allowed_params", {}),
                "default_params": s.get("default_params", {}),
            }
            for s in store.list_sources()
        ]
        mode = "开放模式（未配置密钥）" if not store.list_keys() else "授权模式"
        return json.dumps({"mode": mode, "sources": sources}, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def query_data(
        source_id: str,
        params: dict | None = None,
        filters: dict | None = None,
        api_key: str = "",
        ctx: Context = None,
    ) -> str:
        """按数据源配置的公共查询语句查询外部系统并返回数据集。

        Args:
            source_id: 数据源 ID（先用 list_data_sources 查询）
            params: 查询参数（必须在数据源的参数白名单内），如 {"status": "paid", "limit": 10}
            filters: 对返回数据集的 JSON 等值过滤，如 {"city": "北京"}
            api_key: 公共 Key（stdio 客户端兜底方式；HTTP 客户端建议用请求头）
        """
        store = get_store()

        deny = _check_auth(ctx, api_key, source_id)
        if deny:
            return deny

        source = store.get_source(source_id)
        if source is None:
            return f"错误：数据源 '{source_id}' 不存在。可用: {[s['id'] for s in store.list_sources()]}"

        try:
            safe_params = _coerce_params(source, params or {})
            if source["type"] == "sqlite":
                rows = _query_sqlite(source, safe_params)
            else:
                rows = await _query_http(source, safe_params)
        except Exception as exc:  # noqa: BLE001
            store.add_audit({"key_id": "-", "source": source_id, "ok": False, "rows": 0, "error": str(exc)})
            return f"查询失败: {exc}"

        filtered = _apply_filters(rows[:_MAX_ROWS], filters or {})
        row_limit = int(source.get("row_limit") or 100)
        data = filtered[:row_limit]
        store.add_audit({"key_id": "-", "source": source_id, "ok": True, "rows": len(data), "error": None})

        return json.dumps(
            {
                "source": source_id,
                "total_matched": len(filtered),
                "returned": len(data),
                "truncated": len(filtered) > len(data),
                "data": data,
            },
            ensure_ascii=False,
            default=str,
        )
