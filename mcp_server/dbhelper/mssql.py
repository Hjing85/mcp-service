"""SQL Server Helper（pymssql，参数风格 %(name)s）。"""

from __future__ import annotations

from typing import Any

from .base import DBHelper


class MssqlHelper(DBHelper):
    db_type = "sqlserver"
    param_style = "pyformat"

    @staticmethod
    def _fix_text(value: Any) -> Any:
        """修正 Chinese_PRC 排序规则下 varchar 中文的乱码。

        连接使用 UTF-8 时，服务端返回的 GBK 字节被按 latin-1 解释，
        形如 “电解铜” 变成 “µç½âÍ­”。这里反向还原；
        本身正常的中文无法 encode('latin-1')，会原样保留。
        """
        if not isinstance(value, str):
            return value
        try:
            raw = value.encode("latin-1")
        except UnicodeEncodeError:
            return value
        try:
            return raw.decode("gbk")
        except UnicodeDecodeError:
            return value

    def query(self, sql: str, params: dict | None = None, max_rows: int = 500) -> list[dict]:
        rows = super().query(sql, params, max_rows)
        for row in rows:
            for key, value in row.items():
                row[key] = self._fix_text(value)
        return rows

    def _connect(self) -> Any:
        pymssql = self._require_driver("pymssql", "pymssql")
        cfg = self.cfg
        return pymssql.connect(
            server=cfg["host"],
            port=int(cfg.get("port", 1433)),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg.get("database", "master"),
            charset=cfg.get("charset", "UTF-8"),
            login_timeout=int(cfg.get("login_timeout", 10)),
            timeout=int(cfg.get("timeout", 30)),
            as_dict=False,
        )
