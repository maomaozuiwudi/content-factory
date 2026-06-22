"""
全流程实测脚本 — 模拟用户操作
走模式一（素材驱动），3张测试图 → 选图片输出
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_loader import load_config, resolve_path
from modules.素材分析 import analyze_materials, format_analysis_for_prompt
from modules.vision_analyzer import analyze_all_materials
from modules.copy_engine import CopyEngine
from providers.image import get_provider as get_img_provider

load_config()

print("=" * 60)
print("  小红书内容工坊 — 全流程实测")
print("=" * 60)

# ═══════ 步骤1：准备素材 ═══════
print("\n📦 [步骤1] 准备测试素材（模拟你给素材）")
test_dir = resolve_path("output/test_materials")
os.makedirs(test_dir, exist_ok=True)

from PIL import Image, ImageDraw
test_files = []
for i, (title, color) in enumerate([
    ("VS Code编辑器截图 - 写代码必备", (30, 60, 120)),
    ("Obsidian笔记管理界面", (60, 30, 90)),
    ("Bitwarden密码管理工具", (100, 80, 50)),
]):
    path = os.path.join(test_dir, f"test_{i}.png")
    img = Image.new("RGB", (1080, 1440), color)
    draw = ImageDraw.Draw(img)
    draw.text((200, 600), title, fill=(255, 255, 255))
    img.save(path, "PNG")
    test_files.append(path)
    print(f"  ✅ 素材{i+1}: {title}")

material_paths = test_files

# ═══════ 步骤2：素材给完了？ ═══════
print("\n❓ [确认] 素材给完了吗？ → y")
print("  ✅ 确认完毕，开始处理")

# ═══════ 步骤3：元数据分析 ═══════
print("\n🔍 [步骤2] 分析素材元数据...")
analysis = analyze_materials(material_paths)
print(f"  📊 {analysis['summary']}")

# ═══════ 步骤4：视觉分析（Kimi看图） ═══════
print("\n👁️ [步骤2.5] 视觉分析素材内容...")
vision_descriptions = analyze_all_materials(material_paths)
for path, desc in vision_descriptions.items():
    status = "✅" if not desc.startswith("[") else "⚠️"
    print(f"  {status} {os.path.basename(path)}: {desc[:60]}")

# ═══════ 步骤5：出文案 ═══════
print("\n✍️ [步骤3] 生成文案（带视觉上下文 + AG优化）...")
topic = "开源效率工具推荐"
vision_context = "\n".join([
    f"[{os.path.basename(p)}]: {desc}"
    for p, desc in vision_descriptions.items()
])

ce = CopyEngine()
copy_result = ce.generate_copy(
    topic,
    material_context=format_analysis_for_prompt(analysis),
    visual_context=vision_context,
)

print(f"\n  📌 标题: {copy_result['title']}")
print(f"  📝 正文:")
for line in copy_result['body'].split('\n'):
    if line.strip():
        print(f"     {line.strip()}")
print(f"  🏷️ 标签: {', '.join(copy_result['tags'])}")

# ═══════ 步骤6：选输出类型 ═══════
print("\n❓ [步骤4] 选择输出类型")
print("  1️⃣ 图片")
print("  2️⃣ 视频")
choice = "1"  # 模拟选图片
print(f"  → 用户选: {choice}（图片）")

# ═══════ 步骤7：选引擎 ═══════
print("\n⚙️ [步骤5] 选择生成引擎")
print("  1️⃣ 脚本生成(🆓)")
print("  2️⃣ 即梦AI(需AK/SK)")
engine = "1"  # 脚本
print(f"  → 用户选: {engine}（脚本）")

# ═══════ 步骤8：生成图片 ═══════
print("\n🖼️ [步骤6] 生成图片...")
img_provider = get_img_provider()

cover = img_provider.generate_cover(
    title=copy_result["title"],
    subtitle="效率工具 · 全部开源免费",
    tags=copy_result["tags"][:4],
)
print(f"  ✅ 封面: {cover}")

card = img_provider.generate_card(
    title=copy_result["title"],
    subtitle="打工人必备 · 全部免费开源",
)
print(f"  ✅ 卡片: {card}")

# 拼接图
if len(material_paths) >= 2:
    try:
        stitch = img_provider.stitch_images(material_paths, layout="vertical")
        print(f"  ✅ 拼接图: {stitch}")
    except Exception as e:
        print(f"  ⚠️ 拼接失败: {e}")

# ═══════ 结果汇总 ═══════
print("\n" + "=" * 60)
print("  ✅ 全流程完成！")
print("=" * 60)
print(f"\n📊 费用统计：")
print(f"  DeepSeek文案: ~¥0.0042")
print(f"  Kimi视觉分析: ~¥0.003 × {len(material_paths)}张 = ~¥{0.003*len(material_paths)}")
print(f"  图片生成: 🆓（脚本）")
print(f"  合计: ~¥{0.0042 + 0.003*len(material_paths):.4f}")
print(f"\n📁 产出文件：")
for f in os.listdir(resolve_path("output/images/")):
    if "jimeng" not in f and f.endswith(".png"):
        fpath = os.path.join(resolve_path("output/images/"), f)
        if os.path.getsize(fpath) > 5000:
            print(f"  📄 {f} ({os.path.getsize(fpath)//1024}KB)")
