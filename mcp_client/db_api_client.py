"""MCP Server REST 数据接口客户端（连接 mcp_server 并执行 CRUD）。

用法：
    from mcp_client.db_api_client import MCPDbApiClient

    client = MCPDbApiClient("http://localhost:8000", token="pk_...")  # 无密钥可省略 token
    print(client.list_types())                    # 已配置的数据库类型
    print(client.list_sql("sqlserver"))           # sqlserver 可用的 sql_id
    rows = client.query("sqlserver", "material_tag_print_query", {"TagNo": "A123%"})
    result = client.crud("sqlserver", "demo_update", {"id": 1, "status": "paid"})
"""

from __future__ import annotations

from typing import Any

import httpx


class MCPDbApiError(RuntimeError):
    """服务端返回错误时抛出。"""

    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


class MCPDbApiClient:
    """同步 HTTP 客户端，封装 /api/db/* REST 接口。"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str = "",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}
        self.timeout = timeout

    # ------------------------------------------------------------ 基础请求
    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.request(method, url, **kwargs)
        except httpx.ConnectError as exc:
            raise MCPDbApiError(
                f"无法连接 {url}：MCP Server 未启动？请先运行 python -m mcp_server.run_server（{exc}）", 0
            ) from exc

        try:
            payload = resp.json()
        except ValueError:
            preview = resp.text.strip()[:120]
            raise MCPDbApiError(
                f"服务端返回的不是 JSON（HTTP {resp.status_code}）: {preview!r}。"
                "常见原因：服务端是旧进程（不含 /api/db/* 路由）或地址填错，"
                "请重启 python -m mcp_server.run_server 后再试",
                resp.status_code,
            ) from None

        if resp.status_code >= 400 or not payload.get("ok"):
            message = payload.get("error") or f"HTTP {resp.status_code}"
            if resp.status_code == 401:
                message += "（请在 MCPDbApiClient(token=...) 中填入 /admin 签发的公共 Key，或删除全部密钥进入开放模式）"
            raise MCPDbApiError(message, resp.status_code)
        return payload["data"]

    # ------------------------------------------------------------ 接口封装
    def list_types(self) -> list[dict]:
        """GET /api/db/types —— 已配置的数据库类型与各自可用 sql_id。"""
        return self._request("GET", "/api/db/types")

    def list_sql(self, db_type: str) -> list[str]:
        """GET /api/db/sql —— 指定库的 sql_id 列表。"""
        return self._request("GET", "/api/db/sql", params={"db_type": db_type})

    def query(self, db_type: str, sql_id: str, params: dict | None = None, max_rows: int = 100) -> dict:
        """POST /api/db/query —— 只读查询，返回 {"rows": n, "data": [...]}。"""
        return self._request(
            "POST",
            "/api/db/query",
            json={"db_type": db_type, "sql_id": sql_id, "params": params or {}, "max_rows": max_rows},
        )

    def crud(self, db_type: str, sql_id: str, params: dict | None = None, max_rows: int = 100) -> dict:
        """POST /api/db/crud —— 自动按 SQL 首关键字执行查询或增删改。"""
        return self._request(
            "POST",
            "/api/db/crud",
            json={"db_type": db_type, "sql_id": sql_id, "params": params or {}, "max_rows": max_rows},
        )

    # ------------------------------------------------------------ 便捷方法
    def print_table(self, db_type: str, sql_id: str, params: dict | None = None, max_rows: int = 20) -> None:
        """查询并简单打印为文本表格（读取数据实例的内置展示）。"""
        result = self.query(db_type, sql_id, params, max_rows)
        data = result["data"]
        print(f"[{db_type}/{sql_id}] 共 {result['rows']} 行（最多显示 {min(len(data), max_rows)} 行）")
        if not data:
            print("  (无数据)")
            return
        cols = list(data[0].keys())
        widths = {c: max(len(c), *(len(str(r.get(c, ""))) for r in data)) for c in cols}
        print("  " + " | ".join(c.ljust(widths[c])[:24] for c in cols))
        print("  " + "-+-".join("-" * min(widths[c], 24) for c in cols))
        for r in data:
            print("  " + " | ".join(str(r.get(c, "")).ljust(widths[c])[:24] for c in cols))
