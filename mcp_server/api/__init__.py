"""MCP Server 附带的 REST API（与 MCP 端点同一个 HTTP 服务）。

启动服务后可直接用 HTTP 客户端调用：
    GET  /api/db/types                  已配置的数据库类型
    GET  /api/db/sql?db_type=sqlserver  某库的可用 sql_id 列表
    POST /api/db/crud                   执行 CRUD（JSON body）

若管理后台配置了公共 Key，则请求需携带 Authorization: Bearer pk_...
"""

from .routes import register_api_routes

__all__ = ["register_api_routes"]
