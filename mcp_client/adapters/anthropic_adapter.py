"""Anthropic Claude 适配器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from anthropic import AsyncAnthropic

from .base import BaseAdapter, ToolCall, TurnResult

if TYPE_CHECKING:
    from ..client import MCPTool


class AnthropicAdapter(BaseAdapter):
    name = "anthropic"

    def __init__(self, provider: str, api_key: str, model: str, **kwargs):
        self.provider = provider
        self.model = model
        self.client = AsyncAnthropic(api_key=api_key, **kwargs)

    @staticmethod
    def _convert_tools(tools: list["MCPTool"]) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]

    def append_user_message(self, history: list, content: str) -> None:
        history.append({"role": "user", "content": content})

    def tool_result_messages(self, call: ToolCall, result_text: str) -> list:
        return [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": call.id, "content": result_text}
                ],
            }
        ]

    async def chat(
        self,
        history: list,
        tools: list["MCPTool"],
        sanitized_names: dict[str, str],
        system_prompt: str | None,
    ) -> TurnResult:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": history,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        converted = self._convert_tools(tools)
        if converted:
            kwargs["tools"] = converted

        resp = await self.client.messages.create(**kwargs)

        turn = TurnResult()
        assistant_content = []
        for block in resp.content:
            dumped = block.model_dump()
            assistant_content.append(dumped)
            if getattr(block, "type", None) == "text":
                turn.text = block.text
            elif getattr(block, "type", None) == "tool_use":
                turn.tool_calls.append(
                    ToolCall(id=block.id, name=block.name, args=dict(block.input))
                )
        if turn.tool_calls:
            turn.text = None
        turn.assistant_messages = [{"role": "assistant", "content": assistant_content}]
        return turn
