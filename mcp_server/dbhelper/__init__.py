"""dbhelper：多数据库统一 CRUD 层。

- base.py      抽象基类（连接、查询、执行、参数风格转换）
- mssql.py     SQL Server（pymssql）
- orcle.py     Oracle（python-oracledb 瘦客户端）
- mysql.py     MySQL（pymysql）
- dm.py        达梦 DM8（dmPython）
- sql_loader.py 加载 orclesql/mssql/mysqlsql/dmsql 目录下的 SQL 脚本
- factory.py   按 db_type 读取 config/*.json 创建 Helper
"""

from .base import DBHelper
from .sql_loader import list_sql_ids, get_sql
from .factory import create_helper, load_db_config, DB_CONFIG_FILES

__all__ = [
    "DBHelper",
    "list_sql_ids",
    "get_sql",
    "create_helper",
    "load_db_config",
    "DB_CONFIG_FILES",
]
