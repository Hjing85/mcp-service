"""编程方式调用示例：一句话完成「Agent 连接 MCP Server 并回答问题」。

运行前：1) pip install -r requirements.txt  2) 配置 .env  3) 启动 server:
    python -m mcp_server.run_server
然后运行:
    python examples/ask_once.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_client.adapters.registry import create_adapter
from mcp_client.client import MCPAgentClient, pretty_print


async def main() -> None:
    adapter = create_adapter("deepseek")  # 换成 qwen / glm / kimi / claude / openai 等
    client = MCPAgentClient(
        adapter,
        system_prompt="你是一个智能助手，请尽量使用工具获取真实信息再回答。",
    )
    await client.connect(server_url="http://localhost:8000/mcp")
    try:
        result = await client.chat(
            [],
            "帮我算一下 (1024+2048)*3 等于多少，然后查一下北京现在的天气。",
            max_turns=8,
        )
        pretty_print(result, verbose=True)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
