"""
封面模板 — 调用 local_image 模块生成封面
提供预设模板样式供选择
"""

from modules.local_image import generate_cover


# 预设封面模板
TEMPLATES = {
    "简洁": {
        "title_font_size": 80,
        "subtitle": True,
        "tags": True,
        "border": False,
    },
    "标签风": {
        "title_font_size": 64,
        "subtitle": False,
        "tags": True,
        "border": True,
    },
    "大字报": {
        "title_font_size": 96,
        "subtitle": True,
        "tags": False,
        "border": False,
    },
}


def create_cover(title, subtitle="", tags=None, template="简洁", **kwargs):
    """
    使用预设模板创建封面

    Args:
        title: 标题
        subtitle: 副标题
        tags: 标签列表
        template: 模板名（简洁/标签风/大字报）
        **kwargs: 传递给 generate_cover 的其他参数

    Returns:
        str: 图片路径
    """
    style = TEMPLATES.get(template, TEMPLATES["简洁"])

    if not style.get("subtitle"):
        subtitle = ""
    if not style.get("tags"):
        tags = None

    return generate_cover(
        title=title,
        subtitle=subtitle,
        tags=tags,
        **kwargs,
    )


# 测试
if __name__ == "__main__":
    print("=== 封面模板测试 ===\n")

    for name in TEMPLATES:
        print(f"--- 生成模板: {name} ---")
        path = create_cover(
            title=f"测试{name}封面",
            subtitle="副标题测试文字",
            tags=["测试", "模板", name],
            template=name,
        )
        print(f"  输出: {path}")

    print("\nOK")
