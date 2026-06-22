"""
本地生图模块 — 纯 Pillow 生成

功能：
1. 文字卡片图（标题大字 + 背景色/渐变）
2. 多图拼接（用户给的多张图合成一张）
3. 封面模板（标题 + 副标题 + 标签）

依赖 providers/image/ 插槽层动态切换后端。
"""

import os
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils.config_loader import get, resolve_path
from providers.image import get_provider


# 全局单例 provider
_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider


def generate_card(title, subtitle="", bg_color=None, text_color=None, accent_color=None,
                  width=None, height=None, output_path=None):
    """生成文字卡片图 — 委托给 provider"""
    return _get_provider().generate_card(title, subtitle, bg_color, text_color,
                                         accent_color, width, height, output_path)


def stitch_images(image_paths, layout="grid", output_path=None):
    """多图拼接 — 委托给 provider"""
    return _get_provider().stitch_images(image_paths, layout, output_path)


def generate_cover(title, subtitle="", tags=None, output_path=None):
    """生成小红书封面图 — 委托给 provider"""
    return _get_provider().generate_cover(title, subtitle, tags, output_path)


# 测试
if __name__ == "__main__":
    print("=== 本地生图测试 ===\n")

    print("--- 生成文字卡片 ---")
    card_path = generate_card(
        title="3个让你效率翻倍的工具",
        subtitle="打工人必备 · 全部开源免费",
        bg_color="#1A1A2E",
    )
    print(f"  输出: {card_path}")

    print("\n--- 生成封面 ---")
    cover_path = generate_cover(
        title="效率工具推荐",
        subtitle="用了就回不去的3个神器",
        tags=["效率工具", "开源", "生产力", "打工人"],
    )
    print(f"  输出: {cover_path}")

    print("\n--- 测试拼接 ---")
    try:
        stitch_path = stitch_images(
            [card_path, cover_path, card_path, cover_path],
            layout="grid",
        )
        print(f"  输出: {stitch_path}")
    except Exception as e:
        print(f"  拼接测试: {e}")

    print("\nOK")
