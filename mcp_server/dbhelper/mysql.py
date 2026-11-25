"""MySQL Helper（pymysql，参数风格 %(name)s）。"""

from __future__ import annotations

from typing import Any

from .base import DBHelper


class MysqlHelper(DBHelper):
    db_type = "mysql"
    param_style = "pyformat"

    def _connect(self) -> Any:
        pymysql = self._require_driver("pymysql", "pymysql")
        cfg = self.cfg
        return pymysql.connect(
            host=cfg["host"],
            port=int(cfg.get("port", 3306)),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg.get("database"),
            charset=cfg.get("charset", "utf8mb4"),
            connect_timeout=int(cfg.get("connect_timeout", 10)),
            cursorclass=pymysql.cursors.Cursor,
        )
