"""文本处理工具集。"""


def register(mcp) -> None:
    @mcp.tool()
    def word_count(text: str) -> str:
        """统计文本的字符数（含中文）与词数。"""
        chars = len(text)
        words = len(text.split())
        return f"字符数: {chars}, 词数(按空白切分): {words}"

    @mcp.tool()
    def summarize_head(text: str, limit: int = 100) -> str:
        """截取文本前 N 个字符作为摘要。"""
        snippet = text[:limit]
        suffix = "..." if len(text) > limit else ""
        return snippet + suffix
