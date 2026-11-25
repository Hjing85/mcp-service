"""Provider 注册表：从 config/providers.yaml 加载配置并创建适配器。

新增一个 Agent 平台的两种方式：
  A. 该平台兼容 OpenAI 协议 → 只需在 providers.yaml 加一段配置，零代码
  B. 协议特殊 → 在 adapters/ 下新建适配器并在 _TYPES 中注册
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from .anthropic_adapter import AnthropicAdapter
from .base import BaseAdapter
from .openai_compatible import OpenAICompatibleAdapter

_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "mcp_server" / "config" / "providers.yaml"

_TYPES: dict[str, type[BaseAdapter]] = {
    "openai_compatible": OpenAICompatibleAdapter,
    "anthropic": AnthropicAdapter,
}


def load_providers(config_path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    load_dotenv()  # 支持 .env 中的 API Key
    path = Path(config_path) if config_path else _DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("providers", {})


def build_adapter(cfg: dict) -> BaseAdapter:
    """根据单条 provider 配置（dict）创建适配器。

    供 Web 控制台等场景使用；api_key 可直接写入配置，或通过 api_key_env 从环境变量读取。
    """
    cfg = dict(cfg)
    cfg.pop("id", None)
    cfg.pop("note", None)
    cfg.pop("updated_at", None)
    ptype = cfg.pop("type", "openai_compatible")
    api_key_env = cfg.pop("api_key_env", None) or ""
    api_key = cfg.pop("api_key", "") or os.getenv(api_key_env, "")
    if not api_key:
        raise RuntimeError(
            f"provider '{cfg.get('provider', '?')}' 缺少 API Key（请在配置中填写 api_key 或设置环境变量 {api_key_env or '相应变量'}）"
        )
    cls = _TYPES.get(ptype)
    if cls is None:
        raise KeyError(f"不支持的适配器类型: {ptype}，可用: {', '.join(_TYPES)}")
    cfg.setdefault("provider", "custom")
    return cls(api_key=api_key, **cfg)


def create_adapter(provider: str, config_path: str | Path | None = None) -> BaseAdapter:
    providers = load_providers(config_path)
    if provider not in providers:
        raise KeyError(
            f"未知的 provider: {provider}。可用: {', '.join(providers)} "
            f"(可在 config/providers.yaml 中添加)"
        )
    cfg = dict(providers[provider])
    cfg.setdefault("provider", provider)
    api_key_env = cfg.get("api_key_env", "")
    if not cfg.get("api_key") and not os.getenv(api_key_env or "", ""):
        raise RuntimeError(
            f"provider '{provider}' 需要环境变量 {api_key_env}（可在 .env 中配置）"
        )
    return build_adapter(cfg)
