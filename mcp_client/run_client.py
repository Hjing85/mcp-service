"""MCP Client 命令行入口（交互式 REPL）。

用法：
  # 连接远程 HTTP MCP Server，使用通义千问
  python -m mcp_client.run_client --provider qwen --server-url http://localhost:8000/mcp

  # 以子进程方式启动并连接本地 stdio MCP Server
  python -m mcp_client.run_client --provider deepseek --stdio "python -m mcp_server.run_server --transport stdio"

  # 单条问答模式（非交互）
  python -m mcp_client.run_client --provider glm --server-url http://localhost:8000/mcp --ask "北京现在几点？天气如何？"
"""

import argparse
import asyncio
import shlex

from .adapters.registry import create_adapter
from .client import MCPAgentClient, pretty_print

async def run(args: argparse.Namespace) -> None:
    adapter = create_adapter(args.provider, args.config)
    client = MCPAgentClient(adapter, system_prompt=args.system_prompt)

    stdio_command = shlex.split(args.stdio) if args.stdio else None
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else None

    await client.connect(
        server_url=args.server_url,
        stdio_command=stdio_command,
        http_headers=headers,
        transport=args.transport,
    )

    print(f"[ESPMCP] Provider: {args.provider} ({adapter.name})")
    print(f"[ESPMCP] 已连接 MCP Server，发现 {len(client.tools)} 个工具:")
    for t in client.tools:
        desc = (t.description or "").splitlines()[0][:60]
        print(f"  - {t.name}: {desc}")
    print()

    history: list = []
    try:
        if args.ask:
            result = await client.chat(history, args.ask, max_turns=args.max_turns)
            pretty_print(result, verbose=args.verbose)
            return

        print("交互模式：输入问题与 Agent 对话（/quit 退出，/tools 查看工具）")
        while True:
            try:
                user = input("你> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user:
                continue
            if user in ("/quit", "/exit", "exit"):
                break
            if user == "/tools":
                for t in client.tools:
                    print(f"  - {t.name}: {t.description}")
                continue
            result = await client.chat(history, user, max_turns=args.max_turns)
            pretty_print(result, verbose=args.verbose)
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ESPMCP MCP Client")
    parser.add_argument("--provider", required=True, help="Agent/LLM 提供方（见 config/providers.yaml）")
    parser.add_argument("--server-url", default=None, help="远程 MCP Server 地址，SSE 为 http://host:8000/sse")
    parser.add_argument("--transport", choices=["sse", "streamable-http"], default="sse", help="远程传输协议，默认 SSE")
    parser.add_argument("--stdio", default=None, help='本地 stdio MCP Server 启动命令，如 "python -m mcp_server.run_server --transport stdio"')
    parser.add_argument("--config", default=None, help="providers 配置文件路径（默认 config/providers.yaml）")
    parser.add_argument("--system-prompt", default="你是一个乐于助人的智能助手，可以使用提供的工具回答问题。")
    parser.add_argument("--token", default=None, help="连接 MCP Server 时使用的 Bearer Token")
    parser.add_argument("--ask", default=None, help="单条问答模式：直接提问后退出")
    parser.add_argument("--max-turns", type=int, default=8, help="单次问答最大工具调用轮数")
    parser.add_argument("--verbose", action="store_true", help="打印工具调用过程")
    args = parser.parse_args()

    if not args.server_url and not args.stdio:
        parser.error("必须指定 --server-url 或 --stdio 之一")

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
