"""
OpenAI 文案 Provider — 占位文件
"""


class OpenAICopy:
    """OpenAI API 驱动的文案生成器（待实现）"""

    def generate(self, topic: str, context: str = "") -> dict:
        raise NotImplementedError("OpenAICopy 待实现")

    def generate_title(self, topic: str, count: int = 5) -> list:
        raise NotImplementedError("OpenAICopy 待实现")
