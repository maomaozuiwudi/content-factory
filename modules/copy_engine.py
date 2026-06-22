"""
文案引擎 — 本地模式

核心功能：
1. 读取参考库（风格指南、爆款标题集、避坑清单）
2. 通过 provider 插槽生成标题/文案
3. 去AI化处理（避免AI写作痕迹）
4. 支持素材驱动和主题驱动

依赖 providers/copy/ 插槽层动态切换后端。
"""

import json
import requests
import re
from pathlib import Path

from utils.config_loader import get
from utils.reference_reader import format_references_for_prompt
from providers.copy import get_provider


class CopyEngine:
    """文案引擎 — 通过 provider 插槽调用后端"""

    def __init__(self):
        self._provider = get_provider()

    def generate_title(self, topic, style_hint=""):
        """根据主题生成爆款标题"""
        return self._provider.generate_title(topic, count=3)

    def generate_copy(self, topic, material_context="", visual_context=""):
        """生成完整小红书文案

        Args:
            topic: 主题/关键词
            material_context: 素材元数据描述（尺寸、颜色等）
            visual_context: 视觉分析描述（Kimi 看图后的画面描述）

        Returns:
            dict: {"title": str, "body": str, "tags": list}
        """
        # 合并素材描述和视觉描述
        context_parts = []
        if material_context:
            context_parts.append(f"素材信息:\n{material_context}")
        if visual_context:
            context_parts.append(f"画面描述:\n{visual_context}")

        full_context = "\n\n".join(context_parts)
        return self._provider.generate(topic, context=full_context)

    def generate_suggested_materials(self, topic, copy_text):
        """根据主题和文案，告诉用户需要准备什么素材"""
        system_prompt = (
            "你是一个小红书内容策划。根据文案内容，分析需要配什么素材（图片/视频），"
            "给用户一个清晰的素材清单。\n\n"
            "格式要求：\n"
            "1. 每项一行，格式：【素材N】类型 | 内容描述 | 建议尺寸/格式\n"
            "2. 最后给出整体建议"
        )

        user_prompt = f"主题：{topic}\n文案：{copy_text}\n\n请输出素材需求清单。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # 直接使用 provider 的底层公开 API
        return self._provider.call_llm(messages, max_tokens=1000)

    def generate_material_requirements(self, topic, copy_text):
        """生成结构化素材需求清单，分图片/视频两块展示

        调用 DeepSeek 生成原始建议，但输出格式由代码结构化，
        不依赖AI自觉遵守格式。

        Args:
            topic: 内容主题
            copy_text: 完整文案（标题+正文+标签）

        Returns:
            dict: {
                "image_requirements": ["【素材1】xxx | 用途", ...],
                "video_requirements": ["【镜1】内容 | 时长 | 拍摄建议", ...],
            }
        """
        system_prompt = (
            "你是一个小红书内容策划师。根据文案内容，分析需要配什么素材。\n\n"
            "请按以下两个维度输出：\n\n"
            "===图片素材要求===\n"
            "【素材1】描述 | 用途说明 | 建议格式\n"
            "【素材2】描述 | 用途说明 | 建议格式\n"
            "...\n\n"
            "===视频拍摄要求===\n"
            "【镜1】画面描述 | 建议时长 | 拍摄/剪辑建议\n"
            "【镜2】画面描述 | 建议时长 | 拍摄/剪辑建议\n"
            "...\n\n"
            "注意：\n"
            "1. 如果某个维度不需要素材，写\"无\"\n"
            "2. 图片素材包括：产品图、场景图、截图、封面图等\n"
            "3. 视频拍摄要求考虑：画面内容、运镜、文案配合\n"
            "4. 格式符号 === 和 | 必须保留，代码要靠它们解析"
        )

        user_prompt = f"主题：{topic}\n文案：\n{copy_text}\n\n请按格式输出素材需求清单。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw = self._provider.call_llm(messages, max_tokens=1500)

        # 结构化解析：按 === 分块，按 | 分列
        image_reqs = []
        video_reqs = []
        current_section = None

        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if "===图片素材要求" in stripped or "===图片要求" in stripped:
                current_section = "image"
                continue
            if "===视频拍摄要求" in stripped or "===视频要求" in stripped:
                current_section = "video"
                continue
            if stripped.startswith("【") and current_section == "image":
                image_reqs.append(stripped)
            elif stripped.startswith("【") and current_section == "video":
                video_reqs.append(stripped)
            elif stripped == "无" or stripped == "None":
                continue

        # 保底：如果解析失败但AI给了合理内容，按原始格式打包
        if not image_reqs and not video_reqs:
            # 尝试按段落分割
            paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]
            for p in paragraphs:
                if "图片" in p or "素材" in p:
                    for line in p.split("\n"):
                        line = line.strip()
                        if line and (line.startswith("【") or line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                            image_reqs.append(line.lstrip("1234567890. -•、"))
                elif "视频" in p or "镜" in p or "拍摄" in p:
                    for line in p.split("\n"):
                        line = line.strip()
                        if line and (line.startswith("【") or "镜" in line or line.startswith("-") or line.startswith("•")):
                            video_reqs.append(line.lstrip("1234567890. -•、"))

        if not image_reqs:
            image_reqs = ["无需额外图片素材，文案本身已能传达核心信息"]
        if not video_reqs:
            video_reqs = ["无需视频素材，制作静态图文卡片即可"]

        return {
            "image_requirements": image_reqs,
            "video_requirements": video_reqs,
        }


# 测试
if __name__ == "__main__":
    print("=== 文案引擎测试 ===\n")

    engine = CopyEngine()

    print("--- 测试生成标题 ---")
    titles = engine.generate_title("效率工具推荐")
    for i, t in enumerate(titles, 1):
        print(f"  {i}. {t}")

    print("\n--- 测试生成文案 ---")
    result = engine.generate_copy("效率工具推荐", "几张软件截图")
    print(f"标题: {result['title']}")
    print(f"正文(前200字): {result['body'][:200]}...")
    print(f"标签: {result['tags']}")

    print("\n--- 测试素材需求建议 ---")
    suggestion = engine.generate_suggested_materials(
        "效率工具推荐",
        "推荐3个效率工具，每个都有截图"
    )
    print(suggestion[:300])

    print("\nOK")
