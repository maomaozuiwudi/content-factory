"""
模式一测试：6个视频 → 骨架剪辑 → Kimi视觉分析 → DeepSeek出文案 → 分镜 → 配音 → 合成
自动回答所有 input() 调用，静默跑完全流程。
"""
import sys
import os
import builtins

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)

from utils.config_loader import load_config

load_config()

import sys
_log_file = open(os.path.join(os.path.dirname(__file__), "_test_output.txt"), "w", encoding="utf-8")
_orig_print = builtins.print
def _log_print(*args, **kwargs):
    _orig_print(*args, **kwargs)
    _orig_print(*args, file=_log_file, **kwargs)
    _log_file.flush()
builtins.print = _log_print

# ============================================================
# 模拟 input() — 自动回答所有调用，完整覆盖新流程
# 调用顺序：
#   1. _prompt_duration(len(video_paths))  → "35"     (35秒总时长)
#   2. _prompt_topic("素材关键词/主题")     → ""       (用视觉推断的主题)
#   3. input("文案需要修改吗？(y/n)")       → "n"      (不改文案)
#   4. input("音频路径（直接回车跳过）")     → ""       (跳过配音)
#   5. input("请选择: ")                    → "99"     (超出BGM列表→跳过BGM)
#   6. input("请选择 (1/2), 默认1: ")       → ""       (默认引擎)
# ============================================================
_original_input = builtins.input
_input_queue = ["35", "", "n", "", "99", ""]
_input_idx = [0]


def _mock_input(prompt=""):
    i = _input_idx[0]
    if i < len(_input_queue):
        val = _input_queue[i]
        _input_idx[0] += 1
        print(f"[auto] {prompt}{repr(val)}")
        return val
    # 队列用完 → 切换到手动输入，等用户确认
    print(f"\n{'=' * 60}")
    print(f"  📝 自动回答已用完，后续步骤由您手动操作。")
    print(f"{'=' * 60}")
    return _original_input(prompt)


builtins.input = _mock_input

# ============================================================
# 材料路径 — 6个视频
# ============================================================
MATERIALS_DIR = r"E:\任务\小红书内容工坊\materials"
video_files = [
    "video1_18-14.mp4",
    "video2_18-15a.mp4",
    "video3_18-15b.mp4",
    "video4_18-15c.mp4",
    "video5_18-16a.mp4",
    "video6_18-16b.mp4",
]
material_paths = [os.path.join(MATERIALS_DIR, f) for f in video_files]

# 验证文件存在
missing = [p for p in material_paths if not os.path.exists(p)]
if missing:
    print(f"[❌] 以下素材文件不存在：{missing}")
    print("    请检查 materials/ 目录")
    sys.exit(1)

print(f"[✓] 共 {len(material_paths)} 个素材文件，全部存在")
for p in material_paths:
    size = os.path.getsize(p)
    print(f"     {os.path.basename(p)} ({size / 1024 / 1024:.1f} MB)")

# ============================================================
# 启动工作流
# ============================================================
print("\n" + "=" * 60)
print("  启动小红书内容工坊 — 模式一（素材驱动）")
print("  6个视频 → 骨架剪辑 → Kimi视觉 → DeepSeek文案 → 分镜 → TTS配音 → 合成")
print("=" * 60)

from main import XHSWorkshop

workshop = XHSWorkshop()

print("\n" + "-" * 60)
print("  开始处理...")
print("-" * 60)

try:
    result = workshop.mode_material_driven(material_paths)
    print("\n" + "=" * 60)
    print("  ✅ 模式一全流程完成！")
    print("=" * 60)

    # 打印关键产出
    if result:
        cache = result
        print(f"\n📝 标题: {cache.get('copy', {}).get('title', 'N/A')}")
        if cache.get("video"):
            print(f"🎬 最终视频: {cache['video']}")
        if cache.get("cover"):
            print(f"🖼️ 封面: {cache['cover']}")
        if cache.get("voice_script"):
            n = len(cache["voice_script"])
            print(f"🎤 配音文案: {n} 镜")
        if cache.get("vision_descriptions"):
            n = len(cache["vision_descriptions"])
            print(f"👁️ 视觉分析: {n} 个素材已描述")

except Exception as e:
    print(f"\n[❌] 流程异常中止: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

finally:
    # 恢复原始 input
    builtins.input = _original_input
