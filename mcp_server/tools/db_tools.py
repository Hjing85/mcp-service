"""数据库 CRUD 网关工具（受授权保护）。

授权规则：与 data_query 一致——服务器配置了公共 Key 后，必须携带有效 Key
（HTTP/SSE 用 Authorization: Bearer pk_...，stdio 客户端用 api_key 参数兜底）；
未配置任何 Key 时为开放模式。
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context

from ..admin.storage import get_store
from ..dbhelper import (
    DB_CONFIG_FILES,
    create_helper,
    get_sql,
    list_sql_ids,
)


def _bearer_from_ctx(ctx: Context) -> str | None:
    try:
        req = ctx.request_context.request
        if req is not None:
            auth = req.headers.get("authorization", "")
            if auth.lower().startswith("bearer "):
                return auth[7:].strip()
    except Exception:  # stdio 传输没有 request
        pass
    return None


def _check_auth(ctx: Context, api_key_arg: str) -> str | None:
    store = get_store()
    if not store.list_keys():
        return None  # 开放模式
    if store.verify_key(api_key_arg or _bearer_from_ctx(ctx) or "") is None:
        return "拒绝访问：请携带有效的公共 Key（Authorization: Bearer pk_... 或 api_key 参数）"
    return None


def register(mcp) -> None:
    @mcp.tool()
    def db_list(db_type: str = "", api_key: str = "", ctx: Context = None) -> str:
        """列出服务器已配置的数据库类型及其可用 SQL 脚本（sql_id）。

        Args:
            db_type: 可选，指定单个数据库类型（oracle / sqlserver / mysql / dm），
                留空则返回全部
            api_key: 公共 Key（stdio 客户端兜底；HTTP/SSE 建议用请求头）
        """
        deny = _check_auth(ctx, api_key)
        if deny:
            return deny

        db_type = db_type.strip().lower()
        if db_type and db_type not in DB_CONFIG_FILES:
            return f"错误: 未知的数据库类型 '{db_type}'，可用: {', '.join(DB_CONFIG_FILES)}"

        entries = []
        for name, (filename, _, _) in DB_CONFIG_FILES.items():
            if db_type and name != db_type:
                continue
            entries.append(
                {
                    "db_type": name,
                    "config_file": f"config/{filename}",
                    "sql_ids": list_sql_ids(name),
                }
            )
        return json.dumps({"databases": entries}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def db_crud(
        db_type: str,
        sql_id: str,
        params: dict | None = None,
        max_rows: int = 100,
        api_key: str = "",
        ctx: Context = None,
    ) -> str:
        """执行配置在 SQL 目录中的脚本完成 CRUD。

        Args:
            db_type: 数据库类型（oracle / sqlserver / mysql / dm）
            sql_id: SQL 脚本名（不带 .sql，先用 db_list 查询可用脚本）
            params: SQL 中 :param 占位符对应的参数值，如 {"status": "paid", "top": 10}
            max_rows: 查询返回的最大行数（默认 100，上限 500）
            api_key: 公共 Key（stdio 客户端兜底；HTTP/SSE 建议用请求头）
        """
        deny = _check_auth(ctx, api_key)
        if deny:
            return deny

        try:
            sql = get_sql(db_type, sql_id)
        except (KeyError, FileNotFoundError) as exc:
            return f"错误: {exc}"

        helper = create_helper(db_type)
        try:
            result = helper.crud(sql, params or {}, max_rows=min(max(max_rows, 1), 500))
            result["db_type"] = db_type
            result["sql_id"] = sql_id
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as exc:  # noqa: BLE001
            return f"执行失败 [{db_type}/{sql_id}]: {exc}"
        finally:
            helper.close()
