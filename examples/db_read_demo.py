"""读取数据实例：mcp_client 连接 mcp_server 的 REST 接口并读取数据。

运行前：
1. 启动服务：python -m mcp_server.run_server
2. 确认 mcp_server/config/sqlserver.json 的连接信息正确
3. 运行本脚本：python examples/db_read_demo.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_client.db_api_client import MCPDbApiClient, MCPDbApiError


def main() -> None:
    client = MCPDbApiClient(
        base_url=os.getenv("MCP_BASE_URL", "http://localhost:8000"),
        token=os.getenv("MCP_PUBLIC_KEY", ""),  # 也可直接填 /admin 签发的 pk_...
    )

    # 1. 探测服务端已配置的数据库
    print("=" * 60)
    print("① 服务端已配置的数据库类型：")
    try:
        for entry in client.list_types():
            print(f"  - {entry['db_type']:<10} sql_id: {entry['sql_ids']}")
    except MCPDbApiError as exc:
        print(f"  连接失败: {exc}（请先启动 python -m mcp_server.run_server）")
        return

    # 2. 读取数据（只读查询）
    print("=" * 60)
    print("② 读取示例：sqlserver 物料标签打印记录（模糊匹配标签号）")
    try:
        client.print_table(
            "sqlserver",
            "material_tag_print_query",
            params={"TagNo": "A%"},   # 按实际标签号修改
            max_rows=10,
        )
    except MCPDbApiError as exc:
        print(f"  查询失败: {exc.status} {exc}")

    # 3. CRUD 混合示例：查询 -> 更新 -> 再查询
    print("=" * 60)
    print("③ CRUD 流程示例（demo_select / demo_update，按实际表结构调整）")
    try:
        result = client.crud("sqlserver", "demo_select", {"status": "paid", "top": 5})
        print(f"  查询到 {result['rows']} 行")
        result = client.crud("sqlserver", "demo_update", {"id": 1, "status": "paid"})
        print(f"  更新影响 {result['affected']} 行")
    except MCPDbApiError as exc:
        print(f"  执行失败: {exc.status} {exc}")

    print("=" * 60)
    print("完成。更多用法见 mcp_client/db_api_client.py 模块注释。")


if __name__ == "__main__":
    main()
