"""
卡片模板 — 生成各种风格的文字卡片
提供预设卡片模板样式
"""

from modules.local_image import generate_card


# 预设卡片模板
CARD_TEMPLATES = {
    "深色简约": {
        "bg_color": "#1A1A2E",
        "text_color": "#FFFFFF",
        "accent_color": "#E94560",
    },
    "浅色清新": {
        "bg_color": "#F5F5F5",
        "text_color": "#333333",
        "accent_color": "#4ECDC4",
    },
    "活力橙": {
        "bg_color": "#FF6B35",
        "text_color": "#FFFFFF",
        "accent_color": "#FFD700",
    },
    "极简白": {
        "bg_color": "#FFFFFF",
        "text_color": "#222222",
        "accent_color": "#666666",
    },
    "科技蓝": {
        "bg_color": "#0F3460",
        "text_color": "#FFFFFF",
        "accent_color": "#00D2FF",
    },
}


def create_card(title, subtitle="", template="深色简约", **kwargs):
    """
    使用预设模板创建文字卡片

    Args:
        title: 标题文字
        subtitle: 副标题
        template: 模板名
        **kwargs: 传递给 generate_card 的其他参数

    Returns:
        str: 图片路径
    """
    style = CARD_TEMPLATES.get(template, CARD_TEMPLATES["深色简约"])
    params = {**style, **kwargs}

    return generate_card(
        title=title,
        subtitle=subtitle,
        **params,
    )


# 测试
if __name__ == "__main__":
    print("=== 卡片模板测试 ===\n")

    for name in CARD_TEMPLATES:
        print(f"--- 生成卡片: {name} ---")
        path = create_card(
            title=f"测试{name}卡片",
            subtitle="副标题 - 小红书内容工坊",
            template=name,
        )
        print(f"  输出: {path}")

    print("\nOK")
