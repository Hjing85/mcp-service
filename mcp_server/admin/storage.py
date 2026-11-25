"""服务端授权与数据源配置的持久化存储。

- 数据源(sources)：外部系统的公共查询模板 + 白名单参数
- 公共密钥(keys)：仅保存 SHA-256 哈希，创建时明文只展示一次
- 审计日志(audit)：每次数据查询的记录
"""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any, Optional

DEFAULT_STORE_PATH = Path(__file__).resolve().parents[1] / "config" / "server_store.json"

_AUDIT_CAP = 200


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class AdminStore:
    """线程安全的 JSON 文件存储。"""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else DEFAULT_STORE_PATH
        self._lock = threading.RLock()
        self._data: dict[str, list] = {"sources": [], "keys": [], "audit": []}
        self._load()

    # -------------------------------------------------------------- 基础 IO
    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        for k in ("sources", "keys", "audit"):
            self._data.setdefault(k, [])
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # -------------------------------------------------------------- 数据源
    def list_sources(self) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._data["sources"])

    def get_source(self, source_id: str) -> Optional[dict]:
        with self._lock:
            for s in self._data["sources"]:
                if s["id"] == source_id:
                    return copy.deepcopy(s)
        return None

    def save_source(self, source: dict) -> dict:
        """新增或按 id 更新数据源，返回保存后的记录。"""
        sid = (source.get("id") or "").strip() or f"src_{secrets.token_hex(4)}"
        source["id"] = sid
        required = ["type", "query_template"]
        for field in required:
            if not source.get(field):
                raise ValueError(f"缺少必填字段: {field}")
        if source["type"] not in ("sqlite", "http"):
            raise ValueError("type 仅支持 sqlite / http")
        with self._lock:
            for i, s in enumerate(self._data["sources"]):
                if s["id"] == sid:
                    self._data["sources"][i] = source
                    break
            else:
                self._data["sources"].append(source)
            self._save()
        return copy.deepcopy(source)

    def delete_source(self, source_id: str) -> bool:
        with self._lock:
            before = len(self._data["sources"])
            self._data["sources"] = [s for s in self._data["sources"] if s["id"] != source_id]
            changed = len(self._data["sources"]) != before
            # 同步解除密钥绑定
            for k in self._data["keys"]:
                if source_id in k.get("allowed_sources", []):
                    k["allowed_sources"].remove(source_id)
            if changed:
                self._save()
            return changed

    # -------------------------------------------------------------- 密钥
    def create_key(self, note: str, allowed_sources: list[str]) -> dict:
        """创建公共 Key。返回 {"record": 元数据, "key": 明文（仅此一次）}。"""
        raw = "pk_" + secrets.token_hex(20)
        record = {
            "id": "key_" + secrets.token_hex(4),
            "note": note or "",
            "prefix": raw[:10],
            "key_hash": _hash_key(raw),
            "allowed_sources": allowed_sources or [],
            "enabled": True,
            "created_at": _now(),
        }
        with self._lock:
            self._data["keys"].append(record)
            self._save()
        return {"record": copy.deepcopy(record), "key": raw}

    def verify_key(self, raw_key: str) -> Optional[dict]:
        if not raw_key:
            return None
        h = _hash_key(raw_key.strip())
        with self._lock:
            for k in self._data["keys"]:
                if k["key_hash"] == h and k.get("enabled", True):
                    return copy.deepcopy(k)
        return None

    def list_keys(self) -> list[dict]:
        """返回密钥元数据（不含哈希）。"""
        with self._lock:
            out = []
            for k in self._data["keys"]:
                meta = {key: val for key, val in k.items() if key != "key_hash"}
                out.append(meta)
            return out

    def toggle_key(self, key_id: str) -> Optional[dict]:
        with self._lock:
            for k in self._data["keys"]:
                if k["id"] == key_id:
                    k["enabled"] = not k.get("enabled", True)
                    self._save()
                    return copy.deepcopy(k)
        return None

    def delete_key(self, key_id: str) -> bool:
        with self._lock:
            before = len(self._data["keys"])
            self._data["keys"] = [k for k in self._data["keys"] if k["id"] != key_id]
            changed = len(self._data["keys"]) != before
            if changed:
                self._save()
            return changed

    # -------------------------------------------------------------- 审计
    def add_audit(self, entry: dict) -> None:
        entry["ts"] = _now()
        with self._lock:
            self._data["audit"].insert(0, entry)
            del self._data["audit"][_AUDIT_CAP:]
            self._save()

    def list_audit(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return copy.deepcopy(self._data["audit"][:limit])


# 全局单例，供工具与管理路由共享
_store: Optional[AdminStore] = None


def get_store() -> AdminStore:
    global _store
    if _store is None:
        _store = AdminStore()
    return _store
