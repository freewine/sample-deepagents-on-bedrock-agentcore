from langchain.tools import tool
from langchain_core.tools import BaseTool


@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers"""
    return a + b


LOCAL_TOOLS: dict[str, BaseTool] = {t.name: t for t in [add_numbers]}
