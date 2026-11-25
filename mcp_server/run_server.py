"""启动 MCP Server 的入口。

用法：
  python -m mcp_server.run_server                          # 默认 SSE，端口 8000
  python -m mcp_server.run_server --transport stdio        # stdio 模式（本地 Agent 子进程调用）
  python -m mcp_server.run_server --transport streamable-http
  python -m mcp_server.run_server --port 9000              # 自定义端口

启动后：
  MCP 端点(SSE):  http://<host>:<port>/sse
  管理后台:       http://<host>:<port>/admin
"""

import argparse

from .server import build_server


def main() -> None:
    parser = argparse.ArgumentParser(description="ESPMCP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["sse", "streamable-http", "stdio"],
        default="sse",
        help="传输方式：sse 为远程 Agent 默认方式，streamable-http 为新一代 HTTP 协议，stdio 供本地 Agent",
    )
    parser.add_argument("--host", default="0.0.0.0", help="HTTP 监听地址")
    parser.add_argument("--port", type=int, default=8000, help="HTTP 监听端口")
    args = parser.parse_args()

    mcp = build_server()

    if args.transport == "stdio":
        mcp.run("stdio")
    else:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        endpoint = "/sse" if args.transport == "sse" else "/mcp"
        print(f"[ESPMCP] MCP 端点:  http://{args.host}:{args.port}{endpoint}")
        print(f"[ESPMCP] 管理后台: http://{args.host}:{args.port}/admin")
        mcp.run(args.transport)


if __name__ == "__main__":
    main()
