"""MCP Client 可视化控制台（本地 Web 应用）。

功能：
1. 模型配置：为不同系统（厂商）分别配置 API Key / Base URL / 模型，持久化到 config/client_providers.json
2. 连接配置：MCP Server 地址、传输方式（SSE / streamable-http）、服务端签发的公共 Key
3. 对话：通过 MCPAgentClient 完成多轮工具调用，页面展示工具调用过程

启动：python -m mcp_client.run_webapp
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .adapters.registry import build_adapter, load_providers
from .client import MCPAgentClient

_ROOT = Path(__file__).resolve().parent
_CONFIG_PATH = _ROOT / "config" / "client_providers.json"
_CONSOLE_HTML = Path(__file__).resolve().parent / "console.html"

app = FastAPI(title="ESPMCP Client Console")

# (provider_id, server_url, transport, token) -> {"client": MCPAgentClient, "lock": asyncio.Lock}
_clients: dict[tuple, dict] = {}
# session_id -> {"history": [...]}
_sessions: dict[str, dict] = {}


# ------------------------------------------------------------------ 配置存储
def _load_config() -> dict:
    if not _CONFIG_PATH.exists():
        # 首次运行：以 providers.yaml 的厂商清单作为预置模板（不含密钥）
        seeded = {}
        try:
            for pid, cfg in load_providers().items():
                seeded[pid] = {
                    "id": pid,
                    "type": cfg.get("type", "openai_compatible"),
                    "base_url": cfg.get("base_url", ""),
                    "model": cfg.get("model", ""),
                    "api_key": "",
                    "api_key_env": cfg.get("api_key_env", ""),
                    "note": f"预置模板：{pid}",
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
        except Exception:  # noqa: BLE001
            pass
        _save_config({"providers": seeded})
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(data: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _mask(record: dict) -> dict:
    out = {k: v for k, v in record.items() if k != "api_key"}
    key = record.get("api_key") or ""
    out["has_key"] = bool(key)
    out["key_tail"] = key[-4:] if len(key) > 8 else ""
    return out


# ------------------------------------------------------------------ 模型配置 API
class ProviderBody(BaseModel):
    id: str
    type: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    api_key: str = ""   # 传空表示保留原有密钥
    api_key_env: str = ""
    note: str = ""


@app.get("/api/providers")
def list_providers():
    cfg = _load_config()
    return {"ok": True, "data": {pid: _mask(p) for pid, p in cfg["providers"].items()}}


@app.post("/api/providers")
def save_provider(body: ProviderBody):
    cfg = _load_config()
    pid = body.id.strip()
    if not pid:
        raise HTTPException(400, "provider id 不能为空")
    if body.type not in ("openai_compatible", "anthropic"):
        raise HTTPException(400, "type 仅支持 openai_compatible / anthropic")
    old = cfg["providers"].get(pid, {})
    record = {
        "id": pid,
        "type": body.type,
        "base_url": body.base_url.strip(),
        "model": body.model.strip(),
        "api_key": body.api_key.strip() or old.get("api_key", ""),
        "api_key_env": body.api_key_env.strip(),
        "note": body.note.strip(),
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    if not record["api_key"] and not record["api_key_env"]:
        raise HTTPException(400, "请填写 API Key 或 api_key_env 环境变量名")
    cfg["providers"][pid] = record
    _save_config(cfg)
    return {"ok": True, "data": _mask(record)}


@app.delete("/api/providers/{pid}")
def delete_provider(pid: str):
    cfg = _load_config()
    if pid not in cfg["providers"]:
        raise HTTPException(404, "provider 不存在")
    del cfg["providers"][pid]
    _save_config(cfg)
    return {"ok": True}


# ------------------------------------------------------------------ 连接与对话 API
class ChatBody(BaseModel):
    provider: str
    message: str
    server_url: str = "http://localhost:8000/sse"
    transport: str = "sse"           # sse / streamable-http
    token: str = ""                  # 服务端签发的公共 Key（pk_...）
    session_id: str = "default"
    system_prompt: str = "你是一个乐于助人的智能助手，可以使用提供的工具回答问题。"
    max_turns: int = 8


def _get_client(provider_id: str, server_url: str, transport: str, token: str) -> dict:
    cfg = _load_config()
    if provider_id not in cfg["providers"]:
        raise HTTPException(400, f"provider '{provider_id}' 不存在，请先在页面中配置")
    key = (provider_id, server_url, transport, token)
    slot = _clients.get(key)
    if slot is None:
        slot = {"client": None, "lock": asyncio.Lock(), "error": None}
        _clients[key] = slot
    return slot


async def _ensure_connected(slot: dict, provider_id: str, server_url: str, transport: str, token: str) -> MCPAgentClient:
    if slot["client"] is not None:
        return slot["client"]
    async with slot["lock"]:
        if slot["client"] is not None:
            return slot["client"]
        try:
            adapter = build_adapter(cfg_provider(provider_id))
            client = MCPAgentClient(adapter, system_prompt=None)
            headers = {"Authorization": f"Bearer {token}"} if token else None
            await client.connect(server_url=server_url, http_headers=headers, transport=transport)
            slot["client"] = client
            slot["error"] = None
        except Exception as exc:  # noqa: BLE001
            slot["error"] = str(exc)
            raise HTTPException(502, f"连接 MCP Server 失败: {exc}")
    return slot["client"]


def cfg_provider(provider_id: str) -> dict:
    cfg = _load_config()
    return cfg["providers"][provider_id]


@app.get("/api/tools")
async def list_tools(provider: str, server_url: str, transport: str = "sse", token: str = ""):
    slot = _get_client(provider, server_url, transport, token)
    client = await _ensure_connected(slot, provider, server_url, transport, token)
    return {
        "ok": True,
        "data": [{"name": t.name, "description": t.description} for t in client.tools],
    }


@app.post("/api/chat")
async def chat(body: ChatBody):
    slot = _get_client(body.provider, body.server_url, body.transport, body.token)
    client = await _ensure_connected(slot, body.provider, body.server_url, body.transport, body.token)
    client.system_prompt = body.system_prompt

    session = _sessions.setdefault(body.session_id, {"history": []})
    try:
        result = await client.chat(session["history"], body.message, max_turns=body.max_turns)
    except Exception as exc:  # noqa: BLE001
        # 连接可能已失效（如服务端重启），重置后重试一次
        await _reset_client(slot)
        session["history"].clear()
        client2 = await _ensure_connected(slot, body.provider, body.server_url, body.transport, body.token)
        result = await client2.chat(session["history"], body.message, max_turns=body.max_turns)

    return {
        "ok": True,
        "data": {
            "answer": result.text,
            "steps": result.steps,
            "session_id": body.session_id,
        },
    }


async def _reset_client(slot: dict) -> None:
    async with slot["lock"]:
        if slot["client"] is not None:
            try:
                await slot["client"].close()
            except Exception:  # noqa: BLE001
                pass
        slot["client"] = None


@app.post("/api/reset")
def reset_session(body: dict):
    sid = (body or {}).get("session_id", "default")
    _sessions.pop(sid, None)
    return {"ok": True}


@app.exception_handler(HTTPException)
async def http_error(request, exc: HTTPException):
    return JSONResponse({"ok": False, "error": exc.detail}, status_code=exc.status_code)


@app.exception_handler(Exception)
async def unhandled_error(request, exc: Exception):
    """保证任何异常都返回 JSON，避免前端出现 'Internal S... is not valid JSON'。"""
    return JSONResponse(
        {"ok": False, "error": f"客户端内部错误: {type(exc).__name__}: {exc}"},
        status_code=500,
    )


# ------------------------------------------------------------------ 页面
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(_CONSOLE_HTML.read_text(encoding="utf-8"))


def new_session_id() -> str:
    return uuid.uuid4().hex[:8]
