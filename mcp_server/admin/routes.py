"""管理后台路由：挂在 MCP Server 的 HTTP 服务上（/admin 页面 + /admin/api/* 接口）。"""

from __future__ import annotations

import json
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .storage import AdminStore, get_store

_ADMIN_HTML_PATH = Path(__file__).resolve().parent / "admin.html"


def _ok(data=None) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


async def _json_body(request: Request) -> dict:
    try:
        return json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        return {}


def register_admin_routes(mcp, store: AdminStore | None = None) -> None:
    store = store or get_store()

    # ---------------------------------------------------------- 页面
    @mcp.custom_route("/admin", methods=["GET"])
    async def admin_page(request: Request) -> HTMLResponse:
        return HTMLResponse(_ADMIN_HTML_PATH.read_text(encoding="utf-8"))

    # ---------------------------------------------------------- 数据源 API
    @mcp.custom_route("/admin/api/sources", methods=["GET"])
    async def sources_list(request: Request) -> JSONResponse:
        return _ok(store.list_sources())

    @mcp.custom_route("/admin/api/sources", methods=["POST"])
    async def sources_save(request: Request) -> JSONResponse:
        try:
            saved = store.save_source(await _json_body(request))
            return _ok(saved)
        except ValueError as exc:
            return _err(str(exc))

    @mcp.custom_route("/admin/api/sources/{source_id}", methods=["DELETE"])
    async def sources_delete(request: Request) -> JSONResponse:
        if store.delete_source(request.path_params["source_id"]):
            return _ok()
        return _err("数据源不存在", 404)

    # ---------------------------------------------------------- 密钥 API
    @mcp.custom_route("/admin/api/keys", methods=["GET"])
    async def keys_list(request: Request) -> JSONResponse:
        return _ok(store.list_keys())

    @mcp.custom_route("/admin/api/keys", methods=["POST"])
    async def keys_create(request: Request) -> JSONResponse:
        body = await _json_body(request)
        created = store.create_key(body.get("note", ""), body.get("allowed_sources", []))
        # 明文密钥只在创建响应中出现一次
        return _ok({"record": created["record"], "key": created["key"]})

    @mcp.custom_route("/admin/api/keys/{key_id}/toggle", methods=["POST"])
    async def keys_toggle(request: Request) -> JSONResponse:
        record = store.toggle_key(request.path_params["key_id"])
        if record is None:
            return _err("密钥不存在", 404)
        return _ok(record)

    @mcp.custom_route("/admin/api/keys/{key_id}", methods=["DELETE"])
    async def keys_delete(request: Request) -> JSONResponse:
        if store.delete_key(request.path_params["key_id"]):
            return _ok()
        return _err("密钥不存在", 404)

    # ---------------------------------------------------------- 审计 API
    @mcp.custom_route("/admin/api/audit", methods=["GET"])
    async def audit_list(request: Request) -> JSONResponse:
        limit = int(request.query_params.get("limit", "50"))
        return _ok(store.list_audit(min(max(limit, 1), 200)))
