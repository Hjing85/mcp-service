"""MCP Server 核心构建逻辑。

基于官方 Python SDK，支持三种传输方式：
- sse（默认）：供远程 Agent 通过 HTTP SSE 连接，兼容 Dify / Coze 等平台
- streamable-http：MCP 官方新一代 HTTP 协议
- stdio：供 Claude Desktop / Cursor / Cline 等本地 Agent 以子进程方式连接

同时挂载管理后台（/admin）用于可视化配置数据源、授权密钥与审计日志。
"""

from typing import Any

from mcp.server.fastmcp import FastMCP

from .admin.routes import register_admin_routes
from .admin.storage import get_store
from .api import register_api_routes
from . import tools as server_tools

def register_tools(mcp: FastMCP) -> None:
    server_tools.register_all(mcp)  

def build_server(name: str = "espmcp") -> FastMCP:
    """构建 MCP Server：注册工具 + 挂载管理后台。"""
    mcp = FastMCP(
        name,
        instructions=(
            "ESPMCP 服务器：提供查询、导报表等通用工具，"
            "以及受授权保护的 data_query 数据网关（先用 list_data_sources 探测）。"
        ),
    )
    server_tools.register_all(mcp)
    register_admin_routes(mcp, get_store())
    register_api_routes(mcp)
    return mcp
