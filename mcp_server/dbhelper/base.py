"""数据库 Helper 抽象基类。

约定：
- SQL 统一使用命名占位符 :param，由基类按驱动参数风格自动转换
  （oracledb / dmPython 原生 :name；pymssql / pymysql 需要 %(name)s）
- 每次查询/执行独立取连接并提交，异常向上抛出由 MCP 工具层统一包装
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Optional

_NAMED = re.compile(r"(?<![:\w]):(\w+)")  # 匹配 :param（避开 :: 强转与标识符）


class DBHelper(ABC):
    db_type: str = "sqlserver"
    param_style: str = "named"  # named: :name | pyformat: %(name)s

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._conn: Optional[Any] = None

    # ------------------------------------------------------------ 子类实现
    @abstractmethod
    def _connect(self) -> Any:
        """按配置建立连接（驱动在方法内延迟导入，便于缺驱动时给出友好提示）。"""

    # ------------------------------------------------------------ 连接管理
    def _require_driver(self, module: str, pip_name: str) -> Any:
        try:
            return __import__(module)
        except ImportError as exc:
            raise RuntimeError(
                f"[{self.db_type}] 缺少驱动：请先 pip install {pip_name}"
            ) from exc

    def _ensure_conn(self) -> Any:
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass
            self._conn = None

    # ------------------------------------------------------------ 参数转换
    def _convert(self, sql: str) -> str:
        if self.param_style == "named":
            return sql
        return _NAMED.sub(r"%(\1)s", sql)

    @staticmethod
    def _strip_comments(sql: str) -> str:
        return "\n".join(
            line.split("--")[0] for line in sql.splitlines()
        ).strip()

    @staticmethod
    def detect_operation(sql: str) -> str:
        """根据首关键字判断 query / execute。"""
        head = DBHelper._strip_comments(sql).lstrip().split(None, 1)
        first = (head[0] if head else "").upper()
        return "query" if first in ("SELECT", "WITH") else "execute"

    # ------------------------------------------------------------ CRUD
    def query(self, sql: str, params: dict | None = None, max_rows: int = 500) -> list[dict]:
        conn = self._ensure_conn()
        cur = conn.cursor()
        try:
            cur.execute(self._convert(sql), params or {})
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            rows = cur.fetchmany(max_rows + 1)
            return [dict(zip(cols, row)) for row in rows[:max_rows]]
        finally:
            cur.close()

    def execute(self, sql: str, params: dict | None = None) -> int:
        conn = self._ensure_conn()
        cur = conn.cursor()
        try:
            cur.execute(self._convert(sql), params or {})
            affected = cur.rowcount
            conn.commit()
            return affected if affected and affected > 0 else 0
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    # ------------------------------------------------------------ 便捷封装
    def crud(self, sql: str, params: dict | None = None, max_rows: int = 500) -> dict:
        """按 SQL 首关键字自动选择查询或执行，返回统一结构。"""
        op = self.detect_operation(sql)
        if op == "query":
            rows = self.query(sql, params, max_rows)
            return {"operation": "query", "rows": len(rows), "data": rows}
        affected = self.execute(sql, params)
        return {"operation": op, "affected": affected}
