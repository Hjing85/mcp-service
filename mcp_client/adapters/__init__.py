"""Agent 适配层：把 MCP 工具桥接到不同 Agent/LLM 协议。"""

from .base import BaseAdapter, ToolCall, TurnResult
from .openai_compatible import OpenAICompatibleAdapter
from .anthropic_adapter import AnthropicAdapter
from .registry import load_providers, create_adapter

__all__ = [
    "BaseAdapter",
    "ToolCall",
    "TurnResult",
    "OpenAICompatibleAdapter",
    "AnthropicAdapter",
    "load_providers",
    "create_adapter",
]
