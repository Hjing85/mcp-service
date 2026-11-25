"""OpenAI 兼容协议适配器。

一个适配器覆盖所有 OpenAI 兼容的 Agent/LLM：
OpenAI GPT、DeepSeek、通义千问(DashScope)、Kimi(Moonshot)、智谱 GLM、
豆包(火山方舟)、腾讯混元、MiniMax、百度千帆 ERNIE、xAI、Groq 等。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI

from .base import BaseAdapter, ToolCall, TurnResult

if TYPE_CHECKING:
    from ..client import MCPTool


class OpenAICompatibleAdapter(BaseAdapter):
    name = "openai_compatible"

    def __init__(self, provider: str, api_key: str, base_url: str, model: str, **kwargs):
        self.provider = provider
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, **kwargs)

    # ------------------------------------------------------------------ 工具格式
    @staticmethod
    def _convert_tools(tools: list["MCPTool"], sanitized_names: dict[str, str]) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": sanitized_names.get(t.name, t.name),
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]

    # ------------------------------------------------------------------ 消息格式
    def append_user_message(self, history: list, content: str) -> None:
        history.append({"role": "user", "content": content})

    def tool_result_messages(self, call: ToolCall, result_text: str) -> list:
        return [
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": result_text,
            }
        ]

    # ------------------------------------------------------------------ 模型调用
    async def chat(
        self,
        history: list,
        tools: list["MCPTool"],
        sanitized_names: dict[str, str],
        system_prompt: str | None,
    ) -> TurnResult:
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)

        kwargs: dict[str, Any] = {"model": self.model, "messages": messages}
        converted = self._convert_tools(tools, sanitized_names)
        if converted:
            kwargs["tools"] = converted

        resp = await self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        turn = TurnResult(text=msg.content)

        if msg.tool_calls:
            calls = []
            content_blocks = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))
                content_blocks.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"},
                    }
                )
            assistant_msg["tool_calls"] = content_blocks
            turn.tool_calls = calls
            turn.text = None
        turn.assistant_messages = [assistant_msg]
        return turn
