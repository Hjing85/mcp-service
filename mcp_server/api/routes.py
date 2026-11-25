"""REST CRUD 接口实现（挂在 MCP Server 的 HTTP 服务上）。

示例请求：
    POST /api/db/crud
    {
        "db_type": "sqlserver",
        "sql_id": "demo_select",
        "params": {"status": "paid", "top": 10},
        "max_rows": 100
    }
"""

from __future__ import annotations

import json

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..admin.storage import get_store
from ..dbhelper import DB_CONFIG_FILES, create_helper, get_sql, list_sql_ids

_MAX_ROWS = 500


def _ok(data) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _err(message: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"ok": False, "error": message}, status_code=status)


def _authorized(request: Request) -> bool:
    """配置了公共 Key 时要求 Bearer Token；未配置时开放。"""
    store = get_store()
    if not store.list_keys():
        return True
    auth = request.headers.get("authorization", "")
    raw = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    return store.verify_key(raw) is not None


async def _body_json(request: Request) -> dict:
    try:
        return json.loads(await request.body() or b"{}")
    except json.JSONDecodeError:
        raise ValueError("请求体不是合法 JSON")


def register_api_routes(mcp) -> None:
    # ------------------------------------------------ 数据库类型与 SQL 清单
    @mcp.custom_route("/api/db/types", methods=["GET"])
    async def db_types(request: Request) -> JSONResponse:
        if not _authorized(request):
            return _err("拒绝访问：缺少有效的公共 Key", 401)
        return _ok(
            [
                {"db_type": t, "config_file": f"config/{f}", "sql_ids": list_sql_ids(t)}
                for t, (f, _, _) in DB_CONFIG_FILES.items()
            ]
        )

    @mcp.custom_route("/api/db/sql", methods=["GET"])
    async def db_sql_list(request: Request) -> JSONResponse:
        if not _authorized(request):
            return _err("拒绝访问：缺少有效的公共 Key", 401)
        db_type = request.query_params.get("db_type", "")
        try:
            return _ok({"db_type": db_type, "sql_ids": list_sql_ids(db_type)})
        except KeyError as exc:
            return _err(str(exc))

    # ------------------------------------------------ CRUD 执行接口
    @mcp.custom_route("/api/db/crud", methods=["POST"])
    async def db_crud(request: Request) -> JSONResponse:
        if not _authorized(request):
            return _err("拒绝访问：缺少有效的公共 Key", 401)

        try:
            body = await _body_json(request)
        except ValueError as exc:
            return _err(str(exc))

        db_type = (body.get("db_type") or "").strip()
        sql_id = (body.get("sql_id") or "").strip()
        params = body.get("params") or {}
        max_rows = int(body.get("max_rows") or 100)

        if not db_type or not sql_id:
            return _err("缺少 db_type 或 sql_id")

        try:
            sql = get_sql(db_type, sql_id)
        except (KeyError, FileNotFoundError) as exc:
            return _err(str(exc), 404)

        helper = create_helper(db_type)
        try:
            result = helper.crud(sql, params, max_rows=min(max(max_rows, 1), _MAX_ROWS))
            result.update({"db_type": db_type, "sql_id": sql_id})
            return _ok(result)
        except Exception as exc:  # noqa: BLE001
            return _err(f"执行失败 [{db_type}/{sql_id}]: {exc}", 500)
        finally:
            helper.close()

    # ------------------------------------------------ 单条 SQL 读取接口（便捷查询）
    @mcp.custom_route("/api/db/query", methods=["POST"])
    async def db_query(request: Request) -> JSONResponse:
        if not _authorized(request):
            return _err("拒绝访问：缺少有效的公共 Key", 401)
        try:
            body = await _body_json(request)
        except ValueError as exc:
            return _err(str(exc))
        db_type = (body.get("db_type") or "").strip()
        sql_id = (body.get("sql_id") or "").strip()
        params = body.get("params") or {}
        max_rows = int(body.get("max_rows") or 100)
        try:
            sql = get_sql(db_type, sql_id)
        except (KeyError, FileNotFoundError) as exc:
            return _err(str(exc), 404)
        helper = create_helper(db_type)
        try:
            rows = helper.query(sql, params, max_rows=min(max(max_rows, 1), _MAX_ROWS))
            return _ok({"db_type": db_type, "sql_id": sql_id, "rows": len(rows), "data": rows})
        except Exception as exc:  # noqa: BLE001
            return _err(f"查询失败 [{db_type}/{sql_id}]: {exc}", 500)
        finally:
            helper.close()
