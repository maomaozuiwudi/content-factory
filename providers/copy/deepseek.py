"""
DeepSeek 文案 Provider

从 modules/copy_engine.py 迁移而来，保持原有行为不变。
"""

import re
import json
import requests

from utils.config_loader import get
from utils.reference_reader import format_references_for_prompt


class DeepSeekCopy:
    """DeepSeek API 驱动的文案生成器"""

    def __init__(self):
        self.api_key = get("api_keys.deepseek.api_key", "")
        self.base_url = get("api_keys.deepseek.base_url", "https://api.deepseek.com")
        self.model = get("api_keys.deepseek.model", "deepseek-chat")
        self.temperature = get("api_keys.deepseek.temperature", 0.7)
        # base_url 格式校验
        if self.base_url and not self.base_url.startswith("http"):
            print(f"[⚠️ 文案引擎] base_url 格式异常: {self.base_url}，使用默认值")
            self.base_url = "https://api.deepseek.com"
        self._check_api_key()

    def _check_api_key(self):
        if not self.api_key or self.api_key.startswith("sk-") is False:
            print("[⚠️ 文案引擎] DeepSeek API Key 未配置，将使用模拟模式")

    def call_llm(self, messages, max_tokens=2000):
        """公开调用的底层 LLM 接口

        Args:
            messages: list[dict] — 对话消息列表
            max_tokens: 最大输出 token 数

        Returns:
            str: LLM 返回的文本
        """
        return self._call_deepseek(messages, max_tokens=max_tokens)

    def _call_deepseek(self, messages, max_tokens=2000):
        """调用 DeepSeek API"""
        if not self.api_key or self.api_key.startswith("sk-") is False:
            return self._mock_response(messages)

        url = f"{self.base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[❌ DeepSeek API 调用失败] {e}")
            return self._mock_response(messages)

    def _mock_response(self, messages):
        """模拟模式 — 返回测试用文案"""
        last_msg = messages[-1]["content"] if messages else ""
        print("[🤖 文案引擎] 模拟模式 — 返回测试文案")
        return (
            "# 测试标题：提升工作效率的3个隐藏技巧\n\n"
            "你有没有发现，每天忙得要死，但真正做完的事没几件？\n\n"
            "我整理了3个超好用的效率工具，都是我自己一直在用的。\n\n"
            "## 1. PDF全能助手\n"
            "合并、拆分、压缩、转Word，一个工具全搞定。\n\n"
            "## 2. 起号助手\n"
            "内容规划、定时发布、数据分析，新手做账号必备。\n\n"
            "## 3. 笔记管理工具\n"
            "碎片知识整理成体系，再也不怕信息过载。\n\n"
            "👉 全部开源免费，评论区回复「工具」获取链接\n\n"
            "#效率工具 #开源 #生产力 #打工人必备"
        )

    def generate(self, topic: str, context: str = "") -> dict:
        """生成完整小红书文案

        Args:
            topic: 主题
            context: 额外上下文（素材描述等）

        Returns:
            dict: {"title": str, "body": str, "tags": list}
        """
        ref_context = format_references_for_prompt()

        system_prompt = (
            "你是一个小红书文案写手。生成一篇完整的小红书笔记文案。\n\n"
            "AG优化规则（AEO/GEO，让AI搜索优先引用你的内容）：\n"
            "1. 首段直接给结论 — 前40-80字直接回答核心问题，不铺垫不绕弯\n"
            "2. 正文模块化 — 每块内容独立可提取，用数字/序号分段\n"
            "3. 覆盖关键词 — 自然融入用户可能搜的问句（是什么/怎么做/有什么区别/推荐）\n"
            "4. 用具体数据替代模糊描述（\"提升47%\"而非\"显著提升\"）\n"
            "5. 提供个人真实体验/独特见解，不要通用模板\n"
            "6. 段落控制在50-150字，适配AI摘要截取窗口\n\n"
            "格式要求：\n"
            "1. 先给出标题（加##前缀）\n"
            "2. 正文口语化，带emoji但不要过度\n"
            "3. 段落之间空行，每段2-4句\n"
            "4. 结尾加标签（#标签 格式，3-5个）\n"
            "5. 整体字数300-500字\n\n"
            "去AI化要求：\n"
            "- 不要用『首先/其次/最后』『总的来说』等模板词\n"
            "- 不要用『值得注意的是』『值得一提的是』\n"
            "- 用『我』『你』对话感，不用『我们』\n"
            "- 适当加语气词：啦、嘛、呗、咯\n"
            "- 开头要有钩子（提问/反常识/痛点共鸣）\n"
        )

        if ref_context.strip():
            system_prompt += f"\n参考已有风格、避坑清单和爆款规律：\n{ref_context[:1500]}\n"

        user_parts = [f"主题：{topic}"]
        if context:
            # 如果包含画面描述，加专门指令
            if "画面描述" in context:
                system_prompt += (
                    "\n素材视觉提示：你收到的素材描述中包含 AI 视觉分析的真实画面描述。\n"
                    "- 请根据真实画面内容写文案\n"
                    "- 如果素材是软件截图/界面，就写该软件的功能和使用体验\n"
                    "- 如果素材是产品/穿搭图，就写该产品的使用心得\n"
                    "- 如果素材是文档/文字截图，就引述其中的内容\n"
                    '- 让文案说人话，像真人一样聊画面里的内容\n'
                )
                user_parts.append(f"素材信息与画面描述：{context}")
            else:
                user_parts.append(f"素材描述：{context}")
        else:
            user_parts.append(f"素材描述：无")

        user_prompt = "\n".join(user_parts) + "\n\n请生成完整的小红书笔记文案。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = self._call_deepseek(messages, max_tokens=2000)
        return self._parse_copy(result)

    def generate_title(self, topic: str, count: int = 5) -> list:
        """根据主题生成爆款标题

        Args:
            topic: 主题/关键词
            count: 期望返回的标题数量

        Returns:
            list[str]: 标题列表
        """
        ref_context = format_references_for_prompt()

        system_prompt = (
            "你是一个小红书爆款标题生成器。你的任务是生成吸引点击的标题。\n\n"
            "规则：\n"
            "1. 标题要口语化、有情绪、有悬念\n"
            "2. 善用数字、痛点、对比\n"
            "3. 长度控制在15-25字\n"
            "4. 避免标题党（不要『震惊』『千万不要』等夸张词）\n"
            f"5. 每次生成{count}个标题供选择\n"
        )

        if ref_context.strip():
            system_prompt += f"\n参考已有风格和爆款标题规律：\n{ref_context[:1000]}\n"

        user_prompt = f"主题/素材关键词：{topic}\n\n请生成{count}个爆款标题，每个一行。"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = self._call_deepseek(messages, max_tokens=500)
        titles = [t.strip().strip('"').strip("'").lstrip("1234567890. ") for t in result.split("\n") if t.strip() and not t.startswith("#")]
        return [t for t in titles if t][:count]

    def _parse_copy(self, text):
        """解析文案，提取标题、正文、标签"""
        lines = text.strip().split("\n")

        title = ""
        tags = []
        body_lines = []

        for line in lines:
            stripped = line.strip()
            # 优先提取第一个##开头的行作为标题
            if stripped.startswith("## ") and not title:
                title = stripped.replace("## ", "").strip()
            elif stripped.startswith("##") and not title:
                title = stripped.replace("##", "").strip()
            elif stripped.startswith("#") and not stripped.startswith("##") and len(stripped) > 2:
                # 单#开头且不是标题的行视为标签
                tag_text = stripped.lstrip("#").strip()
                if tag_text:
                    # 按空格/分隔符拆分多个标签
                    for t in re.split(r'[\s,，、]+', tag_text):
                        t = t.strip()
                        if t:
                            tags.append(t)
            else:
                body_lines.append(line)

        if not title:
            for line in lines:
                s = line.strip()
                if s and not s.startswith("#"):
                    title = s
                    break

        body = "\n".join(body_lines).strip()
        body = self._de_ai(body)

        return {
            "title": title or "小红书笔记标题",
            "body": body,
            "tags": tags or ["效率工具", "开源", "生产力"],
        }

    def _de_ai(self, text):
        """去AI化 — 去掉AI写作痕迹"""
        patterns = [
            r"首先[，,、]",
            r"其次[，,、]",
            r"最后[，,、]",
            r"总的来说[，,、:]",
            r"总而言之[，,、:]",
            r"值得注意的是[，,、:]",
            r"值得一提的是[，,、:]",
            r"毋庸置疑[，,、:]",
            r"不可否认[，,、:]",
            r"从.*角度来看[，,、:]",
            r"在.*方面[，,、:]",
            r"对于.*而言[，,、:]",
        ]
        for pat in patterns:
            text = re.sub(pat, "", text)
        return text.strip()
