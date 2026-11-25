"""通用 MCP 客户端核心。

职责：
1. 连接 MCP Server（支持 streamable-http 远程连接 与 stdio 本地子进程两种方式）
2. 通过 MCP 协议发现服务器提供的工具（list_tools），转换为各 Agent 的 function-calling 格式
3. 运行「LLM <-> 工具调用」多轮循环（agentic loop），把工具执行结果回传给 LLM
"""

from __future__ import annotations

import json
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from .adapters.base import BaseAdapter, ToolCall


@dataclass
class MCPTool:
    """从 MCP Server 发现的工具（归一化表示）。"""

    name: str
    description: str
    input_schema: dict


@dataclass
class ConversationResult:
    text: str
    steps: list[dict] = field(default_factory=list)  # 每轮工具调用的记录


class MCPAgentClient:
    """把任意 Agent(LLM) 和任意 MCP Server 桥接起来的客户端。"""

    def __init__(self, adapter: BaseAdapter, system_prompt: Optional[str] = None):
        self.adapter = adapter
        self.system_prompt = system_prompt
        self._stack: Optional[AsyncExitStack] = None
        self.session: Optional[ClientSession] = None
        self.tools: list[MCPTool] = []
        # OpenAI 协议对函数名有 [a-zA-Z0-9_-] 限制，做一层重命名映射
        self._sanitized_names: dict[str, str] = {}
        self._original_names: dict[str, str] = {}

    # ------------------------------------------------------------------ 连接
    async def connect(
        self,
        server_url: Optional[str] = None,
        stdio_command: Optional[list[str]] = None,
        http_headers: Optional[dict[str, str]] = None,
        transport: str = "sse",
    ) -> None:
        """连接 MCP Server。

        - server_url + transport("sse"|"streamable-http")：远程 HTTP 连接
        - stdio_command：本地子进程连接
        """
        self._stack = AsyncExitStack()
        if server_url:
            path = server_url.rstrip("/")
            if transport == "sse" and path.endswith("/mcp"):
                raise ValueError(
                    "SSE 传输应使用 /sse 端点：把 --server-url 改成 http://host:8000/sse；"
                    "若要用 /mcp，请加 --transport streamable-http 并以该模式启动服务端"
                )
            if transport == "streamable-http" and path.endswith("/sse"):
                raise ValueError(
                    "streamable-http 传输应使用 /mcp 端点：把 --server-url 改成 http://host:8000/mcp；"
                    "若要用 /sse，请改用 --transport sse"
                )
            if transport == "sse":
                read, write = await self._stack.enter_async_context(
                    sse_client(server_url, headers=http_headers or {})
                )
            else:
                read, write, _ = await self._stack.enter_async_context(
                    streamablehttp_client(server_url, headers=http_headers or {})
                )
        elif stdio_command:
            params = StdioServerParameters(command=stdio_command[0], args=stdio_command[1:])
            read, write = await self._stack.enter_async_context(stdio_client(params))
        else:
            raise ValueError("必须提供 server_url 或 stdio_command 之一")

        self.session = ClientSession(read, write)
        await self._stack.enter_async_context(self.session)
        await self.session.initialize()
        await self.discover_tools()

    async def close(self) -> None:
        if self._stack:
            await self._stack.aclose()
            self._stack = None
            self.session = None

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def _sanitize(name: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]
        return cleaned or "tool"

    async def discover_tools(self) -> list[MCPTool]:
        assert self.session, "尚未连接 MCP Server"
        result = await self.session.list_tools()
        self.tools = [
            MCPTool(
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema or {"type": "object", "properties": {}},
            )
            for t in result.tools
        ]
        for t in self.tools:
            safe = self._sanitize(t.name)
            self._sanitized_names[t.name] = safe
            self._original_names[safe] = t.name
        return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """按原始名称调用 MCP 工具，返回文本结果。"""
        assert self.session, "尚未连接 MCP Server"
        result = await self.session.call_tool(name, arguments=arguments)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        if result.isError:
            return f"工具执行出错: {'; '.join(parts) or '未知错误'}"
        return "\n".join(parts) or "(工具无文本输出)"

    # ------------------------------------------------------------------ 对话循环
    async def chat(self, history: list[dict], user_message: str, max_turns: int = 8) -> ConversationResult:
        """处理一条用户消息，自动执行 Agent 工具循环，返回最终回答。

        history 为该适配器的原生消息格式，会被原地追加（可跨轮复用上下文）。
        """
        steps: list[dict] = []
        self.adapter.append_user_message(history, user_message)

        for _ in range(max_turns):
            turn = await self.adapter.chat(
                history,
                tools=self.tools,
                sanitized_names=self._sanitized_names,
                system_prompt=self.system_prompt,
            )

            if not turn.tool_calls:
                return ConversationResult(text=turn.text or "", steps=steps)

            history.extend(turn.assistant_messages)
            for call in turn.tool_calls:
                original_name = self._original_names.get(call.name, call.name)
                result_text = await self.call_tool(original_name, call.args)
                steps.append({"tool": original_name, "args": call.args, "result": result_text})
                history.extend(
                    self.adapter.tool_result_messages(call, result_text)
                )

        return ConversationResult(text="(达到最大工具调用轮数仍未给出最终回答)", steps=steps)


def pretty_print(result: ConversationResult, verbose: bool = False) -> None:
    if verbose:
        for s in result.steps:
            print(f"  [工具] {s['tool']}  参数: {json.dumps(s['args'], ensure_ascii=False)}")
            print(f"  [结果] {s['result'][:200]}")
    print(result.text)
