"""适配器基类。

任何 Agent/LLM 平台只要实现 BaseAdapter 的三个方法即可接入本框架：
  1. chat()             —— 调用模型并解析出工具调用意图
  2. append_user_message() —— 以该平台的原生格式追加用户消息
  3. tool_result_messages() —— 以该平台的原生格式构造工具结果消息
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 避免与 client.py 循环导入
    from ..client import MCPTool


@dataclass
class ToolCall:
    """归一化的工具调用请求。"""

    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """一次模型调用后的归一化结果。"""

    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_messages: list[Any] = field(default_factory=list)  # 追加到历史的原生消息


class BaseAdapter(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(
        self,
        history: list[Any],
        tools: list[MCPTool],
        sanitized_names: dict[str, str],
        system_prompt: str | None,
    ) -> TurnResult:
        """调用模型一轮。无工具调用时返回 text；有则返回 tool_calls 与原生 assistant 消息。"""

    @abstractmethod
    def append_user_message(self, history: list[Any], content: str) -> None:
        """以该平台的原生格式把用户消息追加到 history。"""

    @abstractmethod
    def tool_result_messages(self, call: ToolCall, result_text: str) -> list[Any]:
        """构造该平台格式的工具结果消息（可多条）。"""
