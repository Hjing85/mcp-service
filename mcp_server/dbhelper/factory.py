"""数据库工厂：按 db_type 读取 config/*.json 创建对应 Helper。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

_SERVER_DIR = Path(__file__).resolve().parents[1]  # mcp_server/
CONFIG_DIR = _SERVER_DIR / "config"

# db_type -> (配置文件名, Helper 模块名, 类名)
DB_CONFIG_FILES = {
    "oracle": ("orcle.json", "orcle", "OracleHelper"),
    "sqlserver": ("sqlserver.json", "mssql", "MssqlHelper"),
    "mysql": ("mysql.json", "mysql", "MysqlHelper"),
    "dm": ("dm.json", "dm", "DmHelper"),
}


def load_db_config(db_type: str) -> dict:
    entry = DB_CONFIG_FILES.get(db_type)
    if entry is None:
        raise KeyError(
            f"未知数据库类型 '{db_type}'，可用: {', '.join(DB_CONFIG_FILES)}"
        )
    path = CONFIG_DIR / entry[0]
    if not path.exists():
        raise FileNotFoundError(f"数据库配置文件不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def create_helper(db_type: str) -> object:
    """创建数据库 Helper（延迟导入，缺驱动时抛出友好提示）。"""
    entry = DB_CONFIG_FILES.get(db_type)
    if entry is None:
        raise KeyError(
            f"未知数据库类型 '{db_type}'，可用: {', '.join(DB_CONFIG_FILES)}"
        )
    filename, module_name, class_name = entry
    cfg = load_db_config(db_type)
    import importlib

    module = importlib.import_module(f".{module_name}", __package__)
    helper_cls: Callable = getattr(module, class_name)
    return helper_cls(cfg)
