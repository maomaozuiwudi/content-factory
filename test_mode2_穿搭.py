"""
模式二全流程实测 — 主题"穿搭"
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_loader import load_config, resolve_path
from modules.vision_analyzer import analyze_all_materials
from modules.copy_engine import CopyEngine
from modules.search import SearXNGSearch

load_config()

print("=" * 60)
print("  模式二：主题驱动 — 穿搭")
print("=" * 60)

# ═══════ 步骤1：用户给主题 ═══════
topic = "穿搭"
print(f"\n📝 [步骤1] 用户主题: {topic}")

# ═══════ 步骤2：搜索热点 ═══════
print(f"\n🔍 [步骤2] 搜索「{topic}」热点话题...")
searcher = SearXNGSearch()
try:
    search_result = searcher.search_topic(topic)
    print(f"  搜索到 {search_result['total_results']} 条相关内容")
except Exception as e:
    print(f"  [⚠️] 搜索失败: {e}")
    print(f"  跳过搜索，直接出文案")

# ═══════ 步骤3：出文案 ═══════
print(f"\n✍️ [步骤3] 生成穿搭文案（AG优化）...")
ce = CopyEngine()
copy_result = ce.generate_copy(topic, visual_context="")

print(f"\n  📌 标题: {copy_result['title']}")
print(f"\n  📝 正文:")
for line in copy_result['body'].split('\n'):
    if line.strip():
        print(f"     {line.strip()}")
print(f"\n  🏷️ 标签: {', '.join(copy_result['tags'])}")

# ═══════ 步骤4：素材需求清单 ═══════
print(f"\n📋 [步骤4] 你需要准备以下素材：")
print(f"  ┌─────────────────────────────────────")
print(f"  │ 【素材1】穿搭自拍/穿搭视频（全身照最佳）")
print(f"  │ 【素材2】单品特写（包/鞋/配饰）")
print(f"  │ 【素材3】穿搭细节图（布料/领口/袖口）")
print(f"  └─────────────────────────────────────")

# ═══════ 步骤5：无素材 → 全自动 ═══════
print(f"\n❓ 有素材吗？ → n（没有）")
print(f"\n🤖 [步骤5] 全自动生成模式")

# 从文案提取要点，生成卡片
import re
body = copy_result.get("body", "")
title = copy_result.get("title", "")
paragraphs = [p.strip() for p in re.split(r'[。！\n]', body) if len(p.strip()) > 10]
key_points = paragraphs[:4]

print(f"\n[🖼️] 从文案提取 {len(key_points)} 个要点...")
for i, point in enumerate(key_points):
    short = point[:40] + ("..." if len(point) > 40 else "")
    print(f"  要点{i+1}: {short}")

# 生成视觉卡片
print(f"\n[🖼️] 生成封面+卡片...")
from providers.image import get_provider as get_img_provider
img = get_img_provider()

cards = []
for i, pt in enumerate(key_points[:3]):
    short = pt[:25] + ("..." if len(pt) > 25 else "")
    path = img.generate_card(title=f"✨ {short}", subtitle=f"穿搭灵感 · {topic}")
    cards.append(path)
    print(f"  ✅ 穿搭卡片{i+1}: {path}")

cover = img.generate_cover(
    title=title,
    subtitle=f"春夏穿搭 · {topic}灵感",
    tags=copy_result.get("tags", [])[:4],
)
print(f"  ✅ 封面: {cover}")

# ═══════ 结果 ═══════
print("\n" + "=" * 60)
print("  ✅ 模式二完成！")
print("=" * 60)
print(f"\n📊 费用：")
print(f"  DeepSeek文案: ~¥0.0042")
print(f"  图片生成: 🆓（脚本）")
print(f"  合计: ~¥0.0042")
print(f"\n💡 如果你有穿搭照片/视频，可以再给我，")
print(f"    我走模式一带视觉分析+骨架剪辑出更精准的内容")
