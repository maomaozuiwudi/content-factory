"""
穿搭主题：全自动出6张图 + 10秒视频
用户说"不给我素材，你全部自己生成"
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_loader import load_config, get
from modules import local_image
from modules.video_composer import images_to_video

load_config()
out_dir = get("project.output_dir", "output")
os.makedirs(out_dir, exist_ok=True)

# ═══════ 穿搭主题内容 ═══════
TITLE = "别再瞎买基础款了！这3件单品让我衣品提升了80%"

card_contents = [
    # (标题, 副标题)
    ("👔 有设计感的纯色衬衫", "微落肩+圆弧下摆\n高支棉/天丝混纺\n浅蓝/米白/灰蓝"),
    ("👖 会呼吸的直筒休闲裤", "腰臀合身不紧绷\n九分长露脚踝\n垂感面料拉长比例"),
    ("👟 极简百搭小白鞋", "纯白无大logo\n皮质好打理\n搭遍所有单品"),
    ("🎯 3件单品搭配逻辑", "衬衫+休闲裤=通勤风\n衬衫+小白鞋=休闲风\n休闲裤+小白鞋=干净清爽"),
    ("⭐ 衣品提升的捷径", "不靠数量靠搭配\n这3件搞定一周通勤\n其他随心情加配饰"),
]

print("=" * 50)
print("生成穿搭主题图片 + 视频")
print("=" * 50)

# ═══════ 生成6张图 ═══════
print("\n[🖼️] 生成封面...")
cover_path = local_image.generate_cover(
    title=TITLE,
    subtitle="春夏穿搭灵感 · 3件单品搞定通勤",
    tags=["男生穿搭", "基础款", "通勤穿搭", "衣品提升"],
)
print(f"  ✅ 封面: {cover_path}")

card_paths = [cover_path]  # 第1张 = 封面
for i, (ctitle, csub) in enumerate(card_contents):
    print(f"\n[🖼️] 生成卡片{i+1}/{len(card_contents)}...")
    # 交替深色/浅色背景
    bg = "#1a1a2e" if i % 2 == 0 else "#0f3460"
    path = local_image.generate_card(
        title=ctitle,
        subtitle=csub,
        bg_color=bg,
        accent_color="#e94560",
    )
    card_paths.append(path)
    print(f"  ✅ 卡片{i+1}: {path}")

print(f"\n📋 共生成 {len(card_paths)} 张图片")

# ═══════ 生成10秒视频 ═══════
print("\n[🎬] 生成10秒视频...")
video_out = os.path.join(out_dir, "穿搭_10s.mp4")

# 6张图10秒，每张约1.67秒
# 转场用淡入淡出
result = images_to_video(
    image_paths=card_paths,
    output_path=video_out,
    duration_per_image=1.67,
    transition_duration=0.3,
    resolution=(1080, 1920),  # 竖屏小红书
    fps=30,
)
print(f"  ✅ 视频: {result}")

print("\n" + "=" * 50)
print("完成！")
print(f"  📷 6张图: {out_dir}/")
print(f"  🎬 10秒视频: {result}")
for p in card_paths:
    print(f"    - {p}")
print("=" * 50)
