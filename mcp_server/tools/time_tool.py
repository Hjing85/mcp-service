"""时间查询工具。"""

from datetime import datetime, timedelta, timezone

_ZONES = {
    "beijing": timezone(timedelta(hours=8)),
    "shanghai": timezone(timedelta(hours=8)),
    "utc": timezone.utc,
    "london": timezone(timedelta(hours=0)),
    "new_york": timezone(timedelta(hours=-5)),
    "tokyo": timezone(timedelta(hours=9)),
}


def register(mcp) -> None:
    @mcp.tool()
    def current_time(city: str = "beijing") -> str:
        """查询指定城市的当前时间。支持 beijing/utc/london/new_york/tokyo。"""
        tz = _ZONES.get((city or "beijing").lower(), _ZONES["beijing"])
        now = datetime.now(tz)
        return f"{city} 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (UTC{now.strftime('%z')})"
