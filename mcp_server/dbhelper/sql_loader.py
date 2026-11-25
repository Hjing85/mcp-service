"""SQL 脚本加载器（v2：适配 config 迁入 mcp_server 后的新路径）。

目录结构：
    mcp_server/config/
        ├── orclesql/     -> db_type: oracle
        ├── mssql/        -> db_type: sqlserver
        ├── mysqlsql/     -> db_type: mysql
        ├── dmsql/        -> db_type: dm
        └── *.json        数据库连接配置

SQL 双源加载（优先级从高到低）：
1. 各 SQL 目录下的 sql_config.json（{"sql_id": "SQL语句", ...}）
2. 各 SQL 目录下的 *.sql 文件（文件名即 sql_id，兼容原方式）

修改后即时生效（json 按 mtime 缓存，sql 文件同样按 mtime 缓存）。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parents[1]  # mcp_server/
CONFIG_DIR = _SERVER_DIR / "config"

SQL_DIRS: dict[str, str] = {
    "oracle": "orclesql",
    "sqlserver": "mssql",
    "mysql": "mysqlsql",
    "dm": "dmsql",
}

_CACHE: dict[tuple[str, str], tuple[float, str]] = {}
_LOCK = threading.Lock()


def sql_dir(db_type: str) -> Path:
    dirname = SQL_DIRS.get(db_type)
    if dirname is None:
        raise KeyError(f"未知数据库类型 '{db_type}'，可用: {', '.join(SQL_DIRS)}")
    return CONFIG_DIR / dirname


def _json_config_path(db_type: str) -> Path:
    return sql_dir(db_type) / "sql_config.json"


def _load_json(db_type: str) -> dict[str, str]:
    """读取 sql_config.json（带 mtime 缓存；文件不存在返回空）。"""
    path = _json_config_path(db_type)
    if not path.exists():
        return {}
    key = (db_type, "__json__")
    mtime = path.stat().st_mtime
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == mtime:
            return json.loads(cached[1])
    data = json.loads(path.read_text(encoding="utf-8"))
    with _LOCK:
        _CACHE[key] = (mtime, json.dumps(data, ensure_ascii=False))
    return data


def list_sql_ids(db_type: str) -> list[str]:
    """sql_config.json 的键 + .sql 文件名，去重排序。"""
    ids = set(_load_json(db_type).keys())
    directory = sql_dir(db_type)
    if directory.exists():
        ids.update(p.stem for p in directory.glob("*.sql"))
    return sorted(ids)


def get_sql(db_type: str, sql_id: str) -> str:
    """按 sql_id 取 SQL：先查 sql_config.json，再查同名 .sql 文件。"""
    json_sql = _load_json(db_type).get(sql_id)
    if json_sql:
        return json_sql.strip()

    path = sql_dir(db_type) / f"{sql_id}.sql"
    if not path.exists():
        raise FileNotFoundError(
            f"SQL 脚本不存在: {sql_id}，可用 sql_id: {list_sql_ids(db_type) or '无'}"
        )
    key = (db_type, sql_id)
    mtime = path.stat().st_mtime
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
    text = path.read_text(encoding="utf-8")
    with _LOCK:
        _CACHE[key] = (mtime, text)
    return text
