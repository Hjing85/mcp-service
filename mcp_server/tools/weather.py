"""天气查询工具（使用免费开源服务 wttr.in，无需 API Key）。"""

import httpx


def register(mcp) -> None:
    @mcp.tool()
    async def weather(city: str) -> str:
        """查询指定城市的当前天气。示例: weather("北京") 或 weather("Shanghai")"""
        url = f"https://wttr.in/{city}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "curl/8.0"},
                    params={"format": "%l|%c|%t|%h|%w|%p"},
                )
                resp.raise_for_status()
                location, icon, temp, humidity, wind, precip = resp.text.strip().split("|")
                return (
                    f"地点: {location}\n天气: {icon}\n温度: {temp}\n"
                    f"湿度: {humidity}\n风速: {wind}\n降水量: {precip}"
                )
        except Exception as exc:  # noqa: BLE001
            return f"天气查询失败: {exc}"
