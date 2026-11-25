"""达梦 DM8 Helper（dmPython 官方驱动，参数风格 :name 原生）。

注意：dmPython 需要在装有达梦客户端/驱动的环境中安装（pip install dmPython）。
"""

from __future__ import annotations

from typing import Any

from .base import DBHelper


class DmHelper(DBHelper):
    db_type = "dm"
    param_style = "named"

    def _connect(self) -> Any:
        dm = self._require_driver("dmPython", "dmPython")
        cfg = self.cfg
        conn = dm.connect(
            user=cfg["user"],
            password=cfg["password"],
            server=cfg["host"],
            port=int(cfg.get("port", 5236)),
            login_timeout=int(cfg.get("login_timeout", 10)),
        )
        schema = cfg.get("schema")
        if schema:
            cur = conn.cursor()
            try:
                cur.execute(f'SET SCHEMA "{schema}"')
                conn.commit()
            finally:
                cur.close()
        return conn
