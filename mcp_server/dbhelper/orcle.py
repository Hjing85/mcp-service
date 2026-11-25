"""Oracle Helper（python-oracledb 瘦客户端，无需安装 Oracle Client；参数风格 :name 原生）。"""

from __future__ import annotations

from typing import Any

from .base import DBHelper


class OracleHelper(DBHelper):
    db_type = "oracle"
    param_style = "named"

    def _connect(self) -> Any:
        oracledb = self._require_driver("oracledb", "oracledb")
        cfg = self.cfg
        dsn = oracledb.makedsn(
            cfg["host"],
            int(cfg.get("port", 1521)),
            service_name=cfg.get("service_name") or cfg.get("database", "ORCLPDB1"),
        )
        return oracledb.connect(
            user=cfg["user"],
            password=cfg["password"],
            dsn=dsn,
        )
