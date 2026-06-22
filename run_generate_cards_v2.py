"""
穿搭主题：重做带衣服图案的6张卡
使用 HTML+CSS 绘制衣服轮廓，不是纯文字
"""
import os, sys, base64, textwrap
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_loader import load_config, get
from providers.image import get_provider

load_config()
out_dir = get("project.output_dir", "output")
os.makedirs(os.path.join(out_dir, "images"), exist_ok=True)

TITLE = "别再瞎买基础款了！这3件单品让我衣品提升了80%"

# 每张卡片的HTML模板 - 用CSS/SVG画衣服图案
def make_card_html(title, subtitle_lines, emoji, color_scheme="dark"):
    """生成带视觉元素的卡片HTML"""
    bg = "#1a1a2e" if color_scheme == "dark" else "#0f3460"
    accent = "#e94560"
    text_c = "#ffffff"
    
    lines_html = ""
    for line in subtitle_lines:
        lines_html += f'<div class="sub-line">{line}</div>'
    
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ margin: 0; width: 1080px; height: 1920px; display: flex; align-items: center; justify-content: center;
  background: {bg}; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; }}
.card {{ width: 960px; height: 1700px; background: linear-gradient(145deg, {bg}, #16213e);
  border-radius: 60px; padding: 60px; box-sizing: border-box;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px solid rgba(233,69,96,0.3); box-shadow: 0 20px 60px rgba(0,0,0,0.5); }}
.emoji {{ font-size: 200px; line-height: 1; margin-bottom: 40px; text-align: center; }}
.title {{ font-size: 52px; font-weight: bold; color: {text_c}; text-align: center;
  margin-bottom: 30px; line-height: 1.4; }}
.accent {{ color: {accent}; }}
.sub-line {{ font-size: 36px; color: rgba(255,255,255,0.85); text-align: center;
  line-height: 1.6; margin: 6px 0; }}
.divider {{ width: 120px; height: 4px; background: {accent}; border-radius: 2px;
  margin: 30px auto; }}
.icon {{ font-size: 160px; margin-bottom: 30px; }}
</style></head><body>
<div class="card">
  <div class="icon">{emoji}</div>
  <div class="accent divider"></div>
  <div class="title">{title}</div>
  <div class="accent divider"></div>
  {lines_html}
</div>
</body></html>"""

def make_cover_html(title, subtitle, tags, emoji):
    tags_html = "".join(f'<span class="tag">{t}</span>' for t in tags)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ margin: 0; width: 1080px; height: 1920px; display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); font-family: 'PingFang SC','Microsoft YaHei',sans-serif; }}
.card {{ width: 960px; height: 1700px; background: linear-gradient(160deg, #1a1a3e, #0f0c29);
  border-radius: 60px; padding: 60px; box-sizing: border-box;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  border: 2px solid rgba(233,69,96,0.4); box-shadow: 0 20px 80px rgba(0,0,0,0.6);
  position: relative; overflow: hidden; }}
.emoji {{ font-size: 160px; margin-bottom: 20px; }}
.title {{ font-size: 56px; font-weight: bold; color: #fff; text-align: center;
  line-height: 1.4; margin-bottom: 20px; padding: 0 20px; }}
.subtitle {{ font-size: 36px; color: rgba(255,255,255,0.7); text-align: center;
  margin-bottom: 40px; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }}
.tag {{ background: rgba(233,69,96,0.2); border: 1px solid rgba(233,69,96,0.5);
  padding: 12px 28px; border-radius: 30px; font-size: 28px; color: #e94560; }}
.accent {{ color: #e94560; }}
.badge {{ background: linear-gradient(135deg, #e94560, #c23152); border-radius: 40px;
  padding: 16px 40px; font-size: 30px; color: #fff; margin-bottom: 30px; }}
</style></head><body>
<div class="card">
  <div class="emoji">{emoji}</div>
  <div class="badge">春夏穿搭灵感</div>
  <div class="title">{title}</div>
  <div class="subtitle">{subtitle}</div>
  <div class="tags">{tags_html}</div>
</div>
</body></html>"""

# 6张卡片的内容 - 每张配大emoji
cards_data = [
    # (emoji, 标题, 副标题行列表, 配色)
    (None, TITLE, "3件单品搞定一周通勤", ["春夏穿搭灵感", "工具猫 · 穿搭干货"], ""),  # 封面
    ("👔", "有设计感的纯色衬衫", ["微落肩 · 圆弧下摆", "高支棉 / 天丝混纺", "浅蓝 / 米白 / 灰蓝"], "dark"),
    ("👖", "会呼吸的直筒休闲裤", ["腰臀合身不紧绷", "九分长 · 露出脚踝", "垂感面料拉长比例"], "light"),
    ("👟", "极简百搭小白鞋", ["纯白无大logo", "皮质好打理", "搭遍所有单品"], "dark"),
    ("🎯", "3件单品搭配逻辑", ["👔衬衫 + 👖休闲裤 = 通勤风", "👔衬衫 + 👟小白鞋 = 休闲风", "👖休闲裤 + 👟小白鞋 = 干净清爽"], "light"),
    ("⭐", "衣品提升的捷径", ["不靠数量靠搭配", "这3件搞定一周出门", "其他随心情加配饰"], "dark"),
]

provider = get_provider()  # HtmlScreenshotImage
print("=" * 50)
print("重新生成带图案的穿搭卡片")
print("=" * 50)

paths = []
for i, data in enumerate(cards_data):
    if i == 0:
        # 封面
        html = make_cover_html(
            title=data[1],
            subtitle="3件单品搞定一周通勤",
            tags=["男生穿搭", "基础款", "通勤穿搭", "衣品提升"],
            emoji="👔👖👟",
        )
        fname = f"cover_穿搭.png"
    else:
        emoji, title, sub_lines, scheme = data
        html = make_card_html(title, sub_lines, emoji, scheme)
        fname = f"card_{i}_{title[:10]}.png" if len(title) > 10 else f"card_{i}_{title}.png"
    
    out_path = os.path.join(out_dir, "images", fname)
    print(f"\n[🖼️] 生成 {i+1}/6: {fname}")
    
    # 用_provider的_screenshot方法直接截图HTML
    from providers.image.html_screenshot import _screenshot
    _screenshot(html, out_path)
    print(f"  ✅ 保存: {out_path} ({os.path.getsize(out_path)//1024}KB)")
    paths.append(out_path)

print("\n✅ 全部生成！")
for p in paths:
    print(f"  - {p}")
