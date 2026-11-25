"""安全表达式计算工具。"""

import ast
import operator

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARYOPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _eval_node(node: ast.expr) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"不支持的表达式元素: {ast.dump(node)}")


def register(mcp) -> None:
    @mcp.tool()
    def calculator(expression: str) -> str:
        """计算一个数学表达式，仅支持四则运算、取模、幂运算。示例: (2+3)*4**2"""
        try:
            result = _eval_node(ast.parse(expression.strip(), mode="eval"))
        except Exception as exc:  # noqa: BLE001
            return f"错误: {exc}"
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return str(result)
