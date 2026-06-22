"""
参考库读写模块
管理 xhs-content-reference skill 下的参考文件：
  - 风格指南.md
  - 爆款标题集.md
  - 配图偏好.md
  - 避坑清单.md
  - 历史帖子.md
  - 竞品分析.md

功能：读取全部/单个、追加内容、搜索、自动分类保存
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime

from utils.config_loader import get, resolve_path

logger = logging.getLogger(__name__)


# 参考库文件列表及友好名称
REFERENCE_FILES = {
    "风格指南": "风格指南.md",
    "爆款标题集": "爆款标题集.md",
    "配图偏好": "配图偏好.md",
    "避坑清单": "避坑清单.md",
    "历史帖子": "历史帖子.md",
    "竞品分析": "竞品分析.md",
    "爆款文案": "爆款文案.md",
    "AG方法论": "AG方法论.md",
}


def get_reference_dir():
    """获取参考库目录绝对路径"""
    ref_path = get("参考库.path")
    if not ref_path:
        # 默认路径
        ref_path = str(
            Path.home()
            / "AppData/Local/hermes/skills/media/xhs-content-reference/references/"
        )
    return resolve_path(ref_path)


def read_all():
    """读取所有参考库文件内容，返回 {文件名: 内容}"""
    ref_dir = get_reference_dir()
    result = {}
    for name, filename in REFERENCE_FILES.items():
        filepath = Path(ref_dir) / filename
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    result[name] = f.read()
            except (PermissionError, OSError, UnicodeDecodeError) as e:
                logger.warning(f"读取参考库文件失败 {filepath}: {e}")
                result[name] = f"# {name}\n\n（读取失败: {e}）\n"
        else:
            result[name] = f"# {name}\n\n（文件尚未创建）\n"
    return result


def read_one(name):
    """读取单个参考库文件"""
    ref_dir = get_reference_dir()
    filename = REFERENCE_FILES.get(name)
    if not filename:
        raise ValueError(f"未知的参考库文件: {name}，可选: {list(REFERENCE_FILES.keys())}")

    filepath = Path(ref_dir) / filename
    if not filepath.is_file():
        return f"# {name}\n\n（文件尚未创建）\n"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except (PermissionError, OSError, UnicodeDecodeError) as e:
        logger.warning(f"读取参考库文件失败 {filepath}: {e}")
        return f"# {name}\n\n（读取失败: {e}）\n"


def append(name, content):
    """
    追加内容到参考库文件
    自动添加时间戳标记
    """
    ref_dir = get_reference_dir()
    filename = REFERENCE_FILES.get(name)
    if not filename:
        raise ValueError(f"未知的参考库文件: {name}")

    try:
        os.makedirs(ref_dir, exist_ok=True)
    except (PermissionError, OSError) as e:
        logger.error(f"创建参考库目录失败 {ref_dir}: {e}")
        raise

    filepath = Path(ref_dir) / filename

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n\n---\n> 记录时间: {timestamp}\n{content}\n"

    try:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(entry)
    except (PermissionError, OSError) as e:
        logger.error(f"写入参考库文件失败 {filepath}: {e}")
        raise

    return f"已追加到 {filename}"


def search(keyword, name=None):
    """
    在参考库中搜索关键词
    name: 指定搜索某个文件，None表示搜索全部
    返回 [(文件名, 匹配行, 行号), ...]
    """
    ref_dir = get_reference_dir()
    results = []

    targets = [name] if name else REFERENCE_FILES.keys()
    for n in targets:
        filename = REFERENCE_FILES.get(n)
        if not filename:
            continue
        filepath = Path(ref_dir) / filename
        if not filepath.exists():
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if keyword.lower() in line.lower():
                        results.append((n, line.strip(), line_no))
        except (PermissionError, OSError, UnicodeDecodeError) as e:
            logger.warning(f"搜索参考库文件失败 {filepath}: {e}")

    return results


# ---------- 搜索结果的自动分类存储 ----------

# 简单的关键词分类规则
_CLASSIFICATION_RULES = [
    ("风格指南", ["语气", "排版", "调性", "风格", "对标", "账号"]),
    ("爆款标题集", ["标题", "爆款", "赞", "藏", "评", "互动"]),
    ("配图偏好", ["配图", "配色", "颜色", "构图", "prompt", "风格关键词"]),
    ("避坑清单", ["限流", "避坑", "红线", "敏感词", "踩坑", "违规"]),
    ("历史帖子", ["发布", "历史", "帖子", "笔记", "已发"]),
    ("竞品分析", ["竞品", "对标", "分析", "粉丝", "变现"]),
    ("爆款文案", ["文案", "正文", "种草", "教程", "测评", "数据"]),
    ("AG方法论", ["AEO", "GEO", "AI搜索", "搜索引擎优化", "结构化", "SEO", "搜索优化"]),
]


def auto_classify(text):
    """
    根据文本内容，自动判断适合存入哪个参考库文件
    返回文件名（中文友好名）
    """
    scores = {}
    for name, keywords in _CLASSIFICATION_RULES:
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[name] = score

    if not scores:
        return "爆款标题集"  # 默认

    # 返回得分最高的
    return max(scores, key=scores.get)


def save_search_result(query, result_text):
    """
    将搜索结果自动存入参考库
    自动分类 + 追加
    """
    category = auto_classify(result_text)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry_content = (
        f"### 搜索记录: {query}\n"
        f"- 来源: SearXNG自动搜索\n"
        f"- 时间: {timestamp}\n"
        f"- 内容摘要:\n"
        f"  {result_text[:500]}\n"
    )

    result = append(category, entry_content)
    return category, result


def save_output(copy_result, topic):
    """将每次生成的成品自动存入参考库 → 越用越懂用户

    Args:
        copy_result: dict {"title": str, "body": str, "tags": list}
        topic: 本次主题/关键词

    - 标题 → 爆款标题集（累计标题库）
    - 全文 → 历史帖子（内容记录）
    - 自动分类 → 风格指南/配图偏好等
    """
    title = copy_result.get("title", "")
    body = copy_result.get("body", "")
    tags = copy_result.get("tags", [])
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    tag_str = ", ".join(tags)

    # 1️⃣ 标题 → 爆款标题集
    try:
        append("爆款标题集", (
            f"### [{ts}] 主题: {topic}\n"
            f"- 标题: {title}\n"
            f"- 标签: {tag_str}\n"
            f"- 来源: 内容工坊自动保存\n"
        ))
    except Exception as e:
        logger.warning(f"保存标题到参考库失败: {e}")

    # 2️⃣ 全文 → 历史帖子（完整记录）
    try:
        append("历史帖子", (
            f"---\n"
            f"### [{ts}] 主题: {topic}\n"
            f"- 标题: {title}\n"
            f"- 标签: {tag_str}\n"
            f"- 正文:\n"
            f"{body}\n"
        ))
    except Exception as e:
        logger.warning(f"保存全文到参考库失败: {e}")

    # 3️⃣ 自动分类：按内容关键词存到对应参考文件
    for category, keywords in _CLASSIFICATION_RULES:
        try:
            if any(kw in body for kw in keywords):
                # 提取相关段落（含该关键词的句子）
                relevant_lines = []
                for line in body.split("\n"):
                    if any(kw in line for kw in keywords):
                        relevant_lines.append(line.strip())
                if relevant_lines:
                    snippet = "\n".join(relevant_lines[:3])  # 最多3行
                    append(category, (
                        f"### [{ts}] 主题: {topic}\n"
                        f"相关段落:\n"
                        f"{snippet}\n"
                    ))
        except Exception as e:
            logger.warning(f"自动分类保存到 {category} 失败: {e}")

    print(f"  [📚] 成品已自动存入参考库（爆款标题集 + 历史帖子）")


# ---------- 工具函数 ----------

def get_reference_summary():
    """获取参考库摘要（每个文件前200字）"""
    all_refs = read_all()
    summary = {}
    for name, content in all_refs.items():
        # 去掉markdown标记，取前200字
        clean = re.sub(r"[#*>`\[\]]", "", content)
        summary[name] = clean[:200]
    return summary


def format_references_for_prompt():
    """将参考库内容格式化为LLM提示上下文"""
    all_refs = read_all()
    parts = []
    for name, content in all_refs.items():
        # 只取正文部分（去掉标题和注释）
        lines = content.split("\n")
        body = [l for l in lines if not l.startswith("<!--") and not l.startswith(">")]
        text = "\n".join(body).strip()
        if text:
            parts.append(f"=== {name} ===\n{text[:800]}")
    return "\n\n".join(parts)


# 测试
if __name__ == "__main__":
    print("=== 参考库读取测试 ===")
    refs = read_all()
    for name, content in refs.items():
        print(f"\n--- {name} ({len(content)}字) ---")
        print(content[:100] + "...")

    print("\n=== 追加测试 ===")
    result = append("爆款标题集", "测试条目：标题《震惊！》数据1000赞")
    print(result)

    print("\n=== 搜索测试 ===")
    hits = search("标题")
    for n, line, ln in hits[:3]:
        print(f"  [{n}:{ln}] {line}")

    print("\n=== 自动分类测试 ===")
    texts = [
        "这个标题用了数字，点赞很高",
        "配色用深蓝色，大字居中",
        "限流了，因为放了二维码",
        "发帖记录",
    ]
    for t in texts:
        cat = auto_classify(t)
        print(f"  [{cat}] ← {t}")

    print("\n=== 格式化Prompt测试 ===")
    prompt = format_references_for_prompt()
    print(prompt[:300] + "...")
    print("\nOK")
