"""工具注册模块。

新增工具的最简单方式：在本目录新建文件，写一个 register(mcp) 函数，
用 @mcp.tool() 装饰器注册工具，然后在下面 import 并加入 register_all()。
"""

from .calculator import register as register_calculator
from .time_tool import register as register_time
from .weather import register as register_weather
from .text_tools import register as register_text
from .data_query import register as register_data_query
from .db_tools import register as register_db_tools

_REGISTERERS = [
    register_calculator,
    register_time,
    register_weather,
    register_text,
    register_data_query,
    register_db_tools,
]


def register_all(mcp) -> None:
    for fn in _REGISTERERS:
        fn(mcp)
