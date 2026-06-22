"""
小红书内容工坊 — 本地模式主入口
支持两种工作模式：

模式一（素材驱动）：用户给素材 → 分析素材 → 出文案 → 出片
模式二（主题驱动）：用户给主题 → 搜索出文案 → 告诉用户要什么素材 → 等用户给素材 → 出片
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 确保项目根目录在sys.path中
_PROJECT_ROOT = Path(__file__).parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from utils.config_loader import load_config, get, resolve_path, ensure_dirs
from utils.reference_reader import read_all, format_references_for_prompt
from modules.copy_engine import CopyEngine
from modules.local_image import generate_card, generate_cover, stitch_images
from modules.素材分析 import analyze_materials, format_analysis_for_prompt
from modules.search import SearXNGSearch
from modules.video_composer import compose_mixed
from utils.reference_reader import save_output


class XHSWorkshop:
    """小红书内容工坊主控"""

    def __init__(self):
        print("=" * 50)
        print("  小红书内容工坊 — 本地模式")
        print("  工具猫 (maomaozuiwudi)")
        print("=" * 50)

        # 加载配置
        print("\n[📋] 加载配置...")
        load_config()
        ensure_dirs()
        print(f"  工作目录: {get('project.work_dir')}")
        print(f"  参考库: {get('参考库.path')}")

        # 初始化引擎
        print("\n[🔧] 初始化引擎...")
        self.copy_engine = CopyEngine()
        self.searcher = SearXNGSearch()
        print("  ✓ 文案引擎 | ✓ SearXNG搜索 | ✓ MoviePy视频合成")

        # 状态
        self.cache = {}  # 保存工作流程中的中间结果

    # ============================================================
    # 模式一：素材驱动
    # ============================================================

    def mode_material_driven(self, material_paths=None):
        """
        模式一：素材驱动
        1. 用户给素材 → 2. 分析素材 → 3. 按素材类型分流（单视频/多视频/仅图片）
        """
        print("\n" + "=" * 50)
        print("  📦 模式一：素材驱动")
        print("=" * 50)

        # 步骤1：获取素材
        if material_paths is None:
            material_paths = self._prompt_material_paths()

        if not material_paths:
            print("[❌] 无素材，流程终止")
            return None

        # 步骤2：分析素材
        print("\n[🔍] 步骤2：分析素材...")
        analysis = analyze_materials(material_paths)
        print(f"  {analysis['summary']}")
        self.cache["analysis"] = analysis

        # 按素材类型分流
        video_materials = [p for p in material_paths
                           if isinstance(p, str) and p.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
        image_materials = [p for p in material_paths if p not in video_materials]

        if len(video_materials) == 1 and len(image_materials) == 0:
            # ── 单个视频：跳过剪辑合成，只出文案 ──
            print("\n🎬 单个视频素材，跳过视频合成，直接出文案")
            self._handle_single_video(video_materials[0])

        elif video_materials:
            # ── 有多个视频（可带图片）──
            # 问用户素材用途
            print("\n[❓] 素材用途：")
            print("  1️⃣  纯穿衣展示 — 直接骨架剪辑合成")
            print("  2️⃣  带产品展示 — 每镜穿衣前插入产品展示视频")
            usage_choice = input("\n请选择 (1/2): ").strip()
            while usage_choice not in ("1", "2"):
                usage_choice = input("请选择 1（纯穿衣展示）或 2（带产品展示）: ").strip()

            if usage_choice == "1":
                # ── 纯穿衣展示：骨架剪辑+Kimi+合成 ──
                self._handle_multi_video(material_paths, video_materials)
            else:
                # ── 带产品展示：分组→产品固定时长裁剪+穿衣骨架剪辑→交替拼接 ──
                self._handle_multi_video_with_product(material_paths, video_materials)

        else:
            # ── 全是图片：问用户要图片还是视频 ──
            print("\n[❓] 选择输出类型：")
            print("  1️⃣  图片 — 出封面+卡片+拼接图（不生成视频）")
            print("  2️⃣  视频 — 出分镜→配音→合成MP4（需确认文案）")
            output_choice = input("\n请选择 (1/2): ").strip()
            while output_choice not in ("1", "2"):
                print("  请输入 1（图片）或 2（视频）")
                output_choice = input("\n请选择 (1/2): ").strip()
            if output_choice == "1":
                self._handle_images_only(material_paths)
            else:
                self._handle_multi_video(material_paths, [])

        # 保存工作记录
        self._save_session("material_driven")

        print("\n" + "=" * 50)
        print("  ✅ 模式一完成！")
        print("  📁 输出目录: " + resolve_path("output/"))
        print("=" * 50)

        return self.cache

    # ============================================================
    # 模式二：主题驱动
    # ============================================================

    def mode_topic_driven(self, topic=None):
        """
        模式二：主题驱动（重构版）
        1. 用户给主题 → 2. 搜索出文案（完整展示） →
        3. 用户确认文案（y/n+可修改） → 4. 素材需求（分图/视频两块展示） →
        5. 有素材？ → 是:分析→问图/视频→生成 | 否:问图/视频→生成
        """
        print("\n" + "=" * 50)
        print("  🎯 模式二：主题驱动")
        print("=" * 50)

        # 步骤1：获取主题
        if topic is None:
            topic = input("\n📝 请输入内容主题: ").strip()
        if not topic:
            topic = "效率工具推荐"
            print(f"  使用默认主题: {topic}")

        print(f"\n[📌] 主题: {topic}")
        self.cache["topic"] = topic

        # 步骤2：搜索 + 生成文案（完整展示）
        print("\n[🔍] 步骤2：搜索资料 & 生成文案...")
        search_result = self.searcher.search_topic(topic)
        print(f"  搜索到 {search_result['total_results']} 条相关内容")

        copy_result = self.copy_engine.generate_copy(topic, "")
        print("\n" + "─" * 40)
        print("  📄 生成的文案")
        print("─" * 40)
        print(f"\n  📌 标题: {copy_result['title']}")
        print(f"\n  📝 正文:\n{copy_result['body']}")
        if copy_result.get("tags"):
            print(f"\n  🏷️  标签: {' '.join(copy_result['tags'])}")
        print("─" * 40)
        self.cache["copy"] = copy_result
        save_output(copy_result, topic)  # 📚 自动存入参考库

        # 步骤3：用户确认文案
        while True:
            print("\n[✅] 步骤3：确认文案")
            confirm = input("  文案满意吗？(y/n): ").strip().lower()
            if confirm == "y":
                print("  ✅ 文案已确认")
                break
            elif confirm == "n":
                print("\n[✏️] 请描述修改要求：")
                modification = input("  修改意见: ").strip()
                if not modification:
                    print("  未输入修改意见，保持原文案")
                    break
                print(f"\n[🔄] 根据意见重新生成文案: {modification}")
                # 用原主题+修改意见重新生成
                copy_result = self.copy_engine.generate_copy(
                    topic,
                    material_context=f"用户修改要求：{modification}",
                )
                print("\n" + "─" * 40)
                print("  📄 更新后的文案")
                print("─" * 40)
                print(f"\n  📌 标题: {copy_result['title']}")
                print(f"\n  📝 正文:\n{copy_result['body']}")
                if copy_result.get("tags"):
                    print(f"\n  🏷️  标签: {' '.join(copy_result['tags'])}")
                print("─" * 40)
                self.cache["copy"] = copy_result
                save_output(copy_result, topic)
            else:
                print("  请输入 y（满意）或 n（需要修改）")

        # 步骤4：生成素材需求（分图片/视频两块展示）
        print("\n[📋] 步骤4：素材需求分析...")
        full_copy_text = (
            f"标题：{copy_result['title']}\n"
            f"正文：{copy_result['body']}\n"
            f"标签：{' '.join(copy_result.get('tags', []))}"
        )
        material_reqs = self.copy_engine.generate_material_requirements(
            topic, full_copy_text
        )
        self.cache["material_requirements"] = material_reqs

        print("\n" + "─" * 40)
        print("  📋 素材需求清单")
        print("─" * 40)
        print("\n  📷 图片素材要求：")
        if material_reqs["image_requirements"]:
            for item in material_reqs["image_requirements"]:
                print(f"    {item}")
        else:
            print("    （无需额外图片素材）")

        print("\n  🎬 视频拍摄要求：")
        if material_reqs["video_requirements"]:
            for item in material_reqs["video_requirements"]:
                print(f"    {item}")
        else:
            print("    （无需视频素材）")
        print("─" * 40)

        # 步骤5：问用户是否有素材
        print("\n[❓] 步骤5：素材情况")
        while True:
            has_material = input("  你已经有素材了吗？(y/n): ").strip().lower()
            if has_material in ("y", "n"):
                break
            print("  请输入 y（有素材）或 n（没有素材）")

        if has_material == "y":
            # ── 有素材：用户输入路径 → 分析 → 问图/视频 → 生成 ──
            print("\n[📂] 请提供素材路径（图片/视频）")
            material_paths = self._prompt_material_paths(allow_empty=False)

            if material_paths:
                # 分析素材
                print("\n[🔍] 分析素材...")
                analysis = analyze_materials(material_paths)
                print(f"  {analysis['summary']}")
                self.cache["analysis"] = analysis

                # 视觉分析（Kimi 看图）
                print("\n[👁️] 视觉分析素材内容...")
                from modules.vision_analyzer import analyze_all_materials
                vision_descriptions = analyze_all_materials(material_paths)
                for path, desc in vision_descriptions.items():
                    print(f"  {os.path.basename(path)}: {desc}")
                self.cache["vision_descriptions"] = vision_descriptions

                # 重新生成文案（带视觉上下文）
                print("\n[✍️] 基于视觉分析更新文案...")
                vision_context = "\n".join([
                    f"[{os.path.basename(p)}]: {desc}"
                    for p, desc in vision_descriptions.items()
                ])
                copy_result = self.copy_engine.generate_copy(
                    topic,
                    material_context=format_analysis_for_prompt(analysis),
                    visual_context=vision_context,
                )
                print(f"  标题: {copy_result['title']}")
                print(f"  正文(预览): {copy_result['body'][:150]}...")
                self.cache["copy"] = copy_result
                save_output(copy_result, topic)  # 📚 自动存入参考库

                # 按素材类型分流
                video_materials = [p for p in material_paths
                                   if isinstance(p, str) and p.lower().endswith(('.mp4', '.mov', '.avi', '.mkv'))]
                image_materials = [p for p in material_paths if p not in video_materials]

                if len(video_materials) == 1 and len(image_materials) == 0:
                    print("\n🎬 单个视频素材，出标题+文案即可")
                    self._handle_single_video(video_materials[0])
                elif video_materials:
                    self._handle_multi_video(material_paths, video_materials)
                else:
                    # 全是图片：问用户要图片还是视频
                    print("\n[❓] 选择输出类型：")
                    print("  1️⃣  图片 — 出封面+卡片+拼接图（不生成视频）")
                    print("  2️⃣  视频 — 出分镜→配音→合成MP4（需确认文案）")
                    output_choice = input("\n请选择 (1/2): ").strip()
                    while output_choice not in ("1", "2"):
                        print("  请输入 1（图片）或 2（视频）")
                        output_choice = input("\n请选择 (1/2): ").strip()
                    if output_choice == "1":
                        self._handle_images_only(material_paths)
                    else:
                        self._handle_multi_video(material_paths, [])
            else:
                print("\n[⚠️] 未提供有效素材路径，将全自动生成")
                self._handle_no_materials(topic, copy_result)
        else:
            # ── 无素材：问图/视频 → 全自动生成 ──
            self._handle_no_materials(topic, copy_result)

        # 保存工作记录
        self._save_session("topic_driven")

        print("\n" + "=" * 50)
        print("  ✅ 模式二完成！")
        print("  📁 输出目录: " + resolve_path("output/"))
        print("=" * 50)

        return self.cache

    # ============================================================
    # 辅助方法
    # ============================================================

    def _prompt_material_paths(self, allow_empty=False):
        """提示用户输入素材路径
        Args:
            allow_empty: True时空输入返回[]，False时用测试素材
        """
        print("\n📂 请输入素材路径（图片/视频）")
        print("   多个文件用逗号分隔")

        all_paths = []
        while True:
            user_input = input("  路径: ").strip()
            if user_input:
                paths = [p.strip().strip('"').strip("'") for p in user_input.split(",")]
                valid = [p for p in paths if os.path.exists(p)]
                if valid:
                    all_paths.extend(valid)
                    for p in valid:
                        print(f"  ✅ {os.path.basename(p)}")
                else:
                    print("  [⚠️] 没有有效路径")
            elif not all_paths:
                if allow_empty:
                    print("  没有素材？将自动生成视觉内容")
                    return []
                else:
                    print("  未输入素材，使用测试素材")
                    return self._create_test_materials()

            # 已有素材时，问是否给完
            if all_paths:
                done = input("\n素材给完了吗？(y/n): ").strip().lower()
                if done == 'y':
                    break
                print("继续添加素材：")

        return all_paths

    def _prompt_topic(self, prompt_text, default_topic=None, vision_hint=None):
        """提示用户输入主题，不输入则从视觉分析推断"""
        topic = input(f"\n📝 {prompt_text}: ").strip()
        if not topic:
            if vision_hint:
                topic = vision_hint
                print(f"  ↳ 根据画面自动识别主题: {topic}")
            else:
                topic = default_topic or "效率工具推荐"
                print(f"  使用默认主题: {topic}")
        return topic

    def _create_test_materials(self):
        """创建测试素材用于调试"""
        print("\n[🧪] 创建测试素材...")
        test_dir = resolve_path("output/test_materials/")
        os.makedirs(test_dir, exist_ok=True)

        from PIL import Image, ImageDraw

        test_files = []
        for i, (title, color) in enumerate([
            ("效率工具1号", (30, 60, 120)),
            ("开源软件推荐", (60, 30, 90)),
            ("生产力提升", (100, 80, 50)),
        ]):
            path = os.path.join(test_dir, f"test_{i}.png")
            img = Image.new("RGB", (1080, 1440), color)
            draw = ImageDraw.Draw(img)
            draw.text((200, 600), title, fill=(255, 255, 255))
            img.save(path, "PNG")
            test_files.append(path)
            print(f"  创建: {path}")

        print(f"  ✅ 共 {len(test_files)} 个测试素材")
        return test_files

    def _prompt_duration(self, num_videos):
        """问用户想要视频总时长，再均分给每段"""
        print(f"\n⏱️ 你有 {num_videos} 个视频，想要最终视频总时长多久？")
        dur_input = input("  总时长（秒，默认30秒）: ").strip()
        try:
            total = max(10, min(120, int(dur_input))) if dur_input else 30
        except ValueError:
            total = 30
        per = total / max(num_videos, 1)
        print(f"  每段视频约 {per:.0f} 秒，共 {total} 秒")
        return total

    def _prompt_gen_engine(self, gen_type="image"):
        """
        问用户选择生成引擎
        gen_type: "image" 或 "video"
        Returns: "script" 或 "jimeng"
        """
        # 检查即梦是否可用
        jimeng_available = False
        try:
            from modules.jimeng_client import JimengClient
            jc = JimengClient.from_config()
            jimeng_available = jc.ready
        except Exception:
            pass

        print(f"\n[⚙️] {gen_type}生成引擎选择：")
        print(f"  1️⃣  脚本生成(🆓) — {'HTML截图' if gen_type == 'image' else 'MoviePy合成'}")
        label = "即梦AI文生图(需AK/SK)" if gen_type == "image" else "即梦AI文生视频(需AK/SK)"
        print(f"  2️⃣  {label}")

        if not jimeng_available:
            print("  [⚠️] 即梦未配置(ak/sk为空)，选2会自动跳过")

        choice = input("\n请选择 (1/2), 默认1: ").strip() or "1"
        if choice == "2" and jimeng_available:
            return "jimeng"
        return "script"

    def _generate_images(self, copy_result, material_paths, topic=None):
        """根据文案和素材生成配图"""
        # 生成封面
        subtitle = topic or copy_result.get("title", "效率工具推荐")[:30]
        cover_path = generate_cover(
            title=copy_result["title"],
            subtitle=subtitle,
            tags=copy_result["tags"][:4],
        )
        self.cache["cover"] = cover_path

        # 生成卡片
        card_path = generate_card(
            title=copy_result["title"],
            subtitle="效率工具 · 全部开源免费",
        )
        self.cache["card"] = card_path

        # 如果有多个图片素材，拼接
        if len(material_paths) >= 2:
            try:
                stitch_path = stitch_images(material_paths, layout="grid")
                self.cache["stitch"] = stitch_path
            except Exception as e:
                print(f"  [⚠️] 拼接失败: {e}")

    def _handle_single_video(self, video_path):
        """单个视频：Kimi视觉分析 → DeepSeek出文案（不生成视频）"""
        print("\n[👁️] 视觉分析视频内容...")
        from modules.vision_analyzer import analyze_all_materials
        vision_descriptions = analyze_all_materials([video_path])
        for path, desc in vision_descriptions.items():
            print(f"  {os.path.basename(path)}: {desc}")
        self.cache["vision_descriptions"] = vision_descriptions

        # 生成文案（带视觉上下文）
        print("\n[✍️] 根据画面描述生成文案...")
        # 从Kimi视觉分析中推断主题
        vision_hint = None
        for p, desc in vision_descriptions.items():
            short = desc[:40].strip()
            if short and not short.startswith("[视频素材"):
                vision_hint = short
                break
        topic = self._prompt_topic("素材关键词/主题", vision_hint=vision_hint)
        vision_context = "\n".join([
            f"[{os.path.basename(p)}]: {desc}"
            for p, desc in vision_descriptions.items()
        ])
        copy_result = self.copy_engine.generate_copy(
            topic,
            visual_context=vision_context,
        )
        self.cache["copy"] = copy_result
        save_output(copy_result, topic)  # 📚 自动存入参考库

        # 输出文案
        print("\n" + "=" * 40)
        print("  📝 生成文案")
        print("=" * 40)
        print(f"  标题: {copy_result['title']}")
        print(f"  正文:\n{copy_result['body']}")
        print(f"  标签: {', '.join(copy_result['tags'])}")
        print("=" * 40)
        print("\n[📌] 单个视频已完成文案生成，跳过视频合成。")

    def _handle_multi_video(self, material_paths, video_paths):
        """多视频/视频+图片：骨架剪辑→视觉分析→出文案→分镜→配音→合成"""
        # A. 询问目标总时长，再骨架剪辑每个视频
        total_dur = self._prompt_duration(len(video_paths))
        per_video_dur = max(3.0, total_dur / max(len(video_paths), 1))
        shots = []
        skeleton_sizes = []
        if video_paths:
            print(f"\n[🦴] 检测到 {len(video_paths)} 个视频素材，每段约 {per_video_dur:.0f} 秒，运行骨架分析...")
            from providers.video.clip import ClipVideo
            clipper = ClipVideo()
            for v_path in video_paths:
                v_name = os.path.splitext(os.path.basename(v_path))[0]
                v_out = resolve_path(f"output/temp_clips/{v_name}_{datetime.now().strftime('%H%M%S')}.mp4")
                os.makedirs(os.path.dirname(v_out), exist_ok=True)
                try:
                    clipped, avg_size = clipper.clip_video(v_path, v_out, target_duration=per_video_dur)
                    skeleton_sizes.append(avg_size)
                    import cv2
                    cap = cv2.VideoCapture(clipped)
                    v_fps = cap.get(cv2.CAP_PROP_FPS)
                    v_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    cap.release()
                    v_dur = round(v_frames / v_fps, 1) if v_fps > 0 else 5.0
                    shots.append({"type": "video", "path": clipped, "duration": v_dur})
                    print(f"  ✅ 剪辑完成: {os.path.basename(clipped)} ({v_dur}s, 骨架大小={avg_size:.0f})")
                except Exception as e:
                    print(f"  [⚠️] {v_name} 骨架分析失败: {e}，使用原视频")
                    shots.append({"type": "video", "path": v_path, "duration": round(per_video_dur, 1)})
                    skeleton_sizes.append(0)

        # B. 视觉分析所有素材
        print("\n[👁️] 视觉分析所有素材...")
        from modules.vision_analyzer import analyze_all_materials
        vision_descriptions = analyze_all_materials(material_paths)
        for path, desc in vision_descriptions.items():
            print(f"  {os.path.basename(path)}: {desc}")
        self.cache["vision_descriptions"] = vision_descriptions

        # C. 从视觉分析推断主题，出文案
        print("\n[✍️] 生成文案（带视觉上下文）...")
        # 从Kimi视觉分析中提取关键词做主题提示
        vision_keywords = []
        for p, desc in vision_descriptions.items():
            # 取描述的前20个字作为主题线索
            short = desc[:40].strip()
            if short and not short.startswith("[视频素材"):
                vision_keywords.append(short)
        vision_hint = "；".join(vision_keywords[:3]) if vision_keywords else None
        topic = self._prompt_topic("素材关键词/主题", vision_hint=vision_hint)
        vision_context = "这是多段视频素材合集，标题要能覆盖整体内容，不能只针对其中某一个视频。\n" + "\n".join([
            f"[{os.path.basename(p)}]: {desc}"
            for p, desc in vision_descriptions.items()
        ])
        copy_result = self.copy_engine.generate_copy(
            topic,
            material_context=format_analysis_for_prompt(self.cache.get("analysis", {})),
            visual_context=vision_context,
        )
        self.cache["copy"] = copy_result
        print(f"  标题: {copy_result['title']}")
        save_output(copy_result, topic)  # 📚 自动存入参考库

        # D. 不生成封面/卡片，纯视频片段拼接
        # 封面由用户自己在剪映加，工坊只负责剪好视频拼一起

        # E. 按骨架大小从小到大排序分镜（防止远小近大切分镜时视觉跳跃）
        if skeleton_sizes and len(skeleton_sizes) == len(shots):
            paired = list(zip(shots, skeleton_sizes))
            paired.sort(key=lambda x: x[1])  # 按骨架大小升序
            shots = [p[0] for p in paired]
            print("  📐 分镜已按骨架大小从小到大排序")

        # F. 进入配音→BGM→合成通用流程
        self._compose_video(shots, copy_result, vision_descriptions)

    def _compose_video(self, shots, copy_result, vision_descriptions):
        """配音→BGM→合成 通用流程（模式一和带产品展示共用）"""
        if not shots:
            print("[❌] 没有可用素材")
            return

        total_duration = sum(s["duration"] for s in shots)
        num_shots = len(shots)

        # A. 显示分镜表
        print("\n[🎬] 分镜规划：")
        print(f"{'镜#':<6}{'类型':<8}{'时长':<8}{'画面内容'}")
        print("-" * 55)
        for i, s in enumerate(shots):
            icon = "🖼️" if s["type"] == "image" else "🎬"
            name = os.path.basename(s["path"])
            print(f"{i+1:<6}{icon+' '+s['type']:<8}{s['duration']}s{'':<6}{name}")
        print(f"\n总时长：约{total_duration:.0f}秒，共{num_shots}镜")

        # ── 生成漫威风格混剪开头（不计入总时长，作为第一镜） ──
        try:
            print("\n[🎬] 生成漫威风格混剪开头（第一镜）...")
            video_paths = [s["path"] for s in shots if s["type"] == "video"]
            if video_paths:
                from providers.video.clip import ClipVideo
                clipper = ClipVideo()
                
                # 1. 从所有视频提取好帧（骨架一致+大小相似），穿插排列
                per_video_frames = []
                for v_path in video_paths:
                    try:
                        frames = clipper.extract_good_frames(
                            v_path, max_frames=15, consistent_pose=True
                        )
                        per_video_frames.append(frames)
                    except Exception:
                        # 如果某个视频骨架分析失败，跳过
                        pass
                
                all_good_frames = []
                if per_video_frames:
                    # 穿插排列
                    max_per = max(len(f) for f in per_video_frames)
                    for i in range(max_per):
                        for vf in per_video_frames:
                            if i < len(vf):
                                all_good_frames.append(vf[i])
                    print(f"  ✅ 共提取 {len(all_good_frames)} 张好帧（{len(per_video_frames)}个视频穿插）")
                
                if not all_good_frames:
                    # 回退：从第一个视频均匀采样
                    print("  [⚠️] 骨架提取失败，从第一个视频均匀采样帧")
                    import cv2
                    cap = cv2.VideoCapture(video_paths[0])
                    if cap.isOpened():
                        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps_v = cap.get(cv2.CAP_PROP_FPS) or 30
                        frame_dir = resolve_path("output/temp_frames/")
                        os.makedirs(frame_dir, exist_ok=True)
                        step = max(1, total // 60)
                        f_idx = 0
                        while f_idx < total and len(all_good_frames) < 60:
                            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                            ret, frame = cap.read()
                            if ret:
                                out_path = os.path.join(frame_dir, f"frame_{f_idx:06d}.jpg")
                                cv2.imwrite(out_path, frame)
                                all_good_frames.append(out_path)
                            f_idx += step
                        cap.release()
                        print(f"  ✅ 均匀采样 {len(all_good_frames)} 帧")

                # 2. 抽取9个7.5秒连续视频片段做九宫格
                import random
                grid_clips = []
                grid_temp_dir = resolve_path("output/temp_clips/")
                os.makedirs(grid_temp_dir, exist_ok=True)
                grid_videos = video_paths[:]
                random.shuffle(grid_videos)
                
                for i in range(9):
                    v_path = grid_videos[i % len(grid_videos)]
                    try:
                        import cv2
                        cap = cv2.VideoCapture(v_path)
                        total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                        fps_v = cap.get(cv2.CAP_PROP_FPS) or 30
                        cap.release()
                        v_dur = total_f / fps_v if fps_v > 0 else 60
                        if v_dur > 5:
                            start_sec = random.uniform(1, max(2, v_dur - 5))
                        else:
                            start_sec = 0.5
                        clip_name = f"grid_{i+1:02d}.mp4"
                        clip_out = os.path.join(grid_temp_dir, clip_name)
                        import subprocess
                        subprocess.run([
                            "ffmpeg", "-i", v_path, "-ss", str(start_sec),
                            "-t", "7.5", "-c:v", "libx264", "-c:a", "aac",
                            "-y", clip_out
                        ], capture_output=True, timeout=30)
                        if os.path.exists(clip_out) and os.path.getsize(clip_out) > 0:
                            grid_clips.append(clip_out)
                            print(f"  📦 九宫格片段 {i+1}/9")
                    except Exception:
                        continue
                
                if all_good_frames and grid_clips:
                    # 3. 提取标题英文关键词
                    title_en = copy_result.get("title", "FASHION SHOW")
                    import re
                    eng_words = re.findall(r'[A-Za-z]+', title_en)
                    if eng_words:
                        title_en = " ".join(eng_words[:5]).upper()
                    else:
                        title_en = "FASHION SHOW"

                    # 4. 合成漫威风格开头
                    from modules.video_composer import create_marvel_intro
                    intro_path = resolve_path(f"output/temp_clips/intro_{datetime.now().strftime('%H%M%S')}.mp4")
                    intro_duration = 7.0
                    create_marvel_intro(
                        shot_images=all_good_frames,
                        grid_clips=grid_clips,
                        title_text=title_en,
                        output_path=intro_path,
                        resolution=(1080, 1920),
                        fps=30,
                        duration=intro_duration,
                    )

                    # 5. 将开头作为第一镜插入 shots 开头
                    shots.insert(0, {
                        "type": "video",
                        "path": intro_path,
                        "duration": intro_duration,
                    })
                    total_duration += intro_duration
                    print(f"\n  ✅ 漫威开头已插入为第一镜 ({intro_duration}s)")
                else:
                    print("  [⚠️] 无法生成漫威开头（帧或九宫格不足），跳过")
            else:
                print("  [⚠️] 没有视频素材，跳过漫威开头")
        except Exception as e:
            print(f"  [⚠️] 漫威开头生成失败: {e}")
            import traceback
            traceback.print_exc()
            print("  ↳ 跳过漫威开头，继续正常流程")

        # B. 生成配音文案
        print("\n[✍️] 正在生成配音文案（按分镜分配）...")
        if vision_descriptions:
            voice_script = self._generate_shot_voiceover(shots, copy_result, vision_descriptions)
        else:
            voice_script = self._generate_voiceover(copy_result, num_shots)

        print("\n📜 配音文案（初稿）：")
        print("-" * 40)
        for i, line in enumerate(voice_script):
            print(f"【镜{i+1}】{line}")
        print("-" * 40)

        confirm = input("\n文案需要修改吗？(y/n): ").strip().lower()
        if confirm == 'y':
            print("请输入修改后的完整文案（每镜一行，用空行分隔）：")
            lines = []
            while True:
                line = input().strip()
                if line == "":
                    break
                lines.append(line)
            if lines:
                voice_script = lines
            print("✅ 文案已更新")

        self.cache["voice_script"] = voice_script

        # C. 用户自己配音（去掉TTS自动生成）
        print("\n[🎤] 请用你的手机录制配音音频，发送到电脑后输入路径：")
        voiceover_path = None
        while True:
            user_audio = input("音频路径（直接回车跳过）: ").strip().strip('"').strip("'")
            if not user_audio:
                print("  ⚠️ 未提供音频，跳过配音")
                break
            if os.path.exists(user_audio):
                voiceover_path = user_audio
                print(f"  ✅ 音频已加载: {os.path.basename(user_audio)} ({os.path.getsize(user_audio)//1024}KB)")
                break
            else:
                print(f"  ❌ 文件不存在: {user_audio}，请重新输入")

        # D. BGM背景音乐选择
        print("\n[🎵] 背景音乐：")
        bgm_path = None
        bgm_library = resolve_path("references/bgm_library/")
        os.makedirs(bgm_library, exist_ok=True)

        # 列出已有BGM库
        existing_bgms = []
        if os.path.isdir(bgm_library):
            for f in os.listdir(bgm_library):
                if f.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                    full_path = os.path.join(bgm_library, f)
                    size_kb = os.path.getsize(full_path) // 1024
                    existing_bgms.append((full_path, f, size_kb))

        if existing_bgms:
            print("  已有BGM库：")
            for i, (path, name, size) in enumerate(existing_bgms):
                print(f"    {i+1}. {name} ({size}KB)")
            print(f"    {len(existing_bgms)+1}. 提供新的BGM文件")
            print(f"    {len(existing_bgms)+2}. 不要BGM")
            bgm_choice = input("\n请选择: ").strip()
            try:
                idx = int(bgm_choice) - 1
                if 0 <= idx < len(existing_bgms):
                    bgm_path = existing_bgms[idx][0]
                    print(f"  ✅ 已选择: {existing_bgms[idx][1]}")
                elif idx == len(existing_bgms):
                    # 提供新BGM
                    new_bgm = input("BGM文件路径: ").strip().strip('"').strip("'")
                    if new_bgm and os.path.exists(new_bgm):
                        import shutil
                        from datetime import datetime
                        new_name = f"bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}{os.path.splitext(new_bgm)[1]}"
                        dst = os.path.join(bgm_library, new_name)
                        shutil.copy2(new_bgm, dst)
                        bgm_path = dst
                        print(f"  ✅ BGM已保存到库: {new_name}")
                    else:
                        print("  ⚠️ 文件不存在，跳过BGM")
            except ValueError:
                print("  ⚠️ 输入无效，跳过BGM")
        else:
            # 没有已有BGM库
            print("  📂 BGM库为空，提供BGM文件路径，或直接回车跳过：")
            new_bgm = input("BGM路径: ").strip().strip('"').strip("'")
            if new_bgm and os.path.exists(new_bgm):
                import shutil
                from datetime import datetime
                new_name = f"bgm_{datetime.now().strftime('%Y%m%d_%H%M%S')}{os.path.splitext(new_bgm)[1]}"
                dst = os.path.join(bgm_library, new_name)
                shutil.copy2(new_bgm, dst)
                bgm_path = dst
                print(f"  ✅ BGM已保存到库: {new_name}")
            else:
                print("  ⚠️ 跳过BGM")

        # E. 选择生成引擎 → 合成最终视频
        engine = self._prompt_gen_engine("video")

        if engine == "jimeng":
            print("\n[🤖] 使用即梦AI生成视频...")
            from modules.jimeng_client import generate_video as jimeng_gen_video

            # 从文案生成一个视频提示词
            topic = self.cache.get("topic") or copy_result.get("title", "")
            video_prompt = f"{copy_result['title']}，{topic}，动态展示"
            result = jimeng_gen_video(video_prompt)
            if "urls" in result and result["urls"]:
                import requests
                video_url = result["urls"][0]
                output_path = resolve_path(
                    f"output/videos/jimeng_{datetime.now().strftime('%H%M%S')}.mp4"
                )
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                resp = requests.get(video_url, stream=True, timeout=30)
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.cache["video"] = output_path
                print(f"\n✅ 即梦视频已生成: {output_path}")
            else:
                print(f"  [⚠️] 即梦生视频失败: {result.get('error', '未知错误')}，回退到脚本合成")
                # 回退到脚本合成
                result = compose_mixed(
                    shots=shots,
                    output_path=resolve_path(
                        f"output/videos/{copy_result['title'][:20]}_{datetime.now().strftime('%H%M%S')}.mp4"
                    ),
                    voiceover_path=voiceover_path,
                    bgm_path=bgm_path,
                    resolution=(1080, 1920),
                )
                self.cache["video"] = result
                print(f"\n✅ 视频已生成: {result}")
        else:
            # 脚本生成（原逻辑：MoviePy合成）
            print("\n[🎬] 合成最终视频（MoviePy）...")
            output_path = resolve_path(
                f"output/videos/{copy_result['title'][:20]}_{datetime.now().strftime('%H%M%S')}.mp4"
            )
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            result = compose_mixed(
                shots=shots,
                output_path=output_path,
                voiceover_path=voiceover_path,
                bgm_path=bgm_path,
                resolution=(1080, 1920),
            )
            self.cache["video"] = result
            print(f"\n✅ 视频已生成: {output_path}")

        # 缓存偏好信息，供 _save_session 写入用户偏好
        self.cache["bgm_path"] = bgm_path
        self.cache["voiceover_path"] = voiceover_path
        self.cache["shots"] = shots
        self.cache["total_duration"] = sum(s["duration"] for s in shots)

    def _handle_multi_video_with_product(self, material_paths, video_paths):
        """多视频带产品展示：用户分组 → 产品固定时长裁剪 + 穿衣骨架剪辑 → 交替拼接"""
        # 分离图片素材
        image_paths = [p for p in material_paths if p not in video_paths]

        # A. 问用户哪些是穿衣视频、哪些是产品展示视频
        print("\n[📋] 请按顺序输入素材类型（输入序号，用逗号分隔）")
        print("  你的素材列表：")
        for i, p in enumerate(video_paths):
            print(f"    {i+1}. {os.path.basename(p)}")

        print("\n  请说明哪些是穿衣展示、哪些是产品展示：")
        print("   例：穿衣展示:1,2,3 | 产品展示:4,5,6")

        clothing_input = input("穿衣展示（序号，逗号分隔）: ").strip()
        product_input = input("产品展示（序号，逗号分隔）: ").strip()

        # 解析序号
        def parse_indices(s):
            indices = []
            for part in s.split(","):
                part = part.strip()
                if part:
                    try:
                        idx = int(part) - 1  # 转0-based
                        if 0 <= idx < len(video_paths):
                            indices.append(idx)
                    except ValueError:
                        pass
            return indices

        clothing_indices = parse_indices(clothing_input)
        product_indices = parse_indices(product_input)

        # 验证
        all_indices = set(clothing_indices + product_indices)
        if len(all_indices) != len(video_paths):
            print("  ⚠️ 分组不完整或重复，强制按前一半穿衣、后一半产品分配")
            mid = len(video_paths) // 2
            clothing_indices = list(range(mid))
            product_indices = list(range(mid, len(video_paths)))

        if len(clothing_indices) != len(product_indices):
            print("  ⚠️ 穿衣和产品数量不匹配，按最少数量配对")
            n = min(len(clothing_indices), len(product_indices))
            clothing_indices = clothing_indices[:n]
            product_indices = product_indices[:n]

        # B. 询问总时长，然后每对（产品+穿衣）的总时长 = total_dur / clothing_count
        total_dur = self._prompt_duration(len(clothing_indices))

        pairs = []
        for ci, pi in zip(clothing_indices, product_indices):
            pair_dur = total_dur / len(clothing_indices)
            product_dur = pair_dur * 0.2  # 1:4 → 产品占20%
            clothing_dur = pair_dur * 0.8  # 穿衣占80%
            pairs.append({
                "product_path": video_paths[pi],
                "clothing_path": video_paths[ci],
                "product_duration": product_dur,
                "clothing_duration": clothing_dur,
            })

        print(f"\n  📊 每对时长分配（共 {len(pairs)} 对）：")
        for i, pair in enumerate(pairs):
            print(f"    第{i+1}对: 产品展示 {pair['product_duration']:.1f}s + 穿衣展示 {pair['clothing_duration']:.1f}s")

        # C. 处理产品展示视频（只做固定时长裁剪，不用骨架）
        print("\n[✂️] 处理产品展示视频（固定时长裁剪）...")

        product_shots = []
        for pair in pairs:
            p_path = pair["product_path"]
            p_name = os.path.splitext(os.path.basename(p_path))[0]
            p_out = resolve_path(f"output/temp_clips/{p_name}_product_{datetime.now().strftime('%H%M%S')}.mp4")
            os.makedirs(os.path.dirname(p_out), exist_ok=True)

            # 用 ffmpeg 直接裁剪固定时长（从视频中间取一段）
            try:
                import subprocess
                import cv2
                # 先获取视频时长
                cap = cv2.VideoCapture(p_path)
                p_fps = cap.get(cv2.CAP_PROP_FPS)
                p_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                p_dur = p_frames / p_fps if p_fps > 0 else 10.0

                # 从中间取片段
                mid_point = max(0, p_dur / 2 - pair["product_duration"] / 2)
                subprocess.run([
                    "ffmpeg", "-i", p_path, "-ss", str(mid_point),
                    "-t", str(pair["product_duration"]),
                    "-c:v", "libx264", "-c:a", "aac",
                    "-y", p_out
                ], capture_output=True, timeout=60)

                # 检查输出文件
                if os.path.exists(p_out):
                    clip_dur = pair["product_duration"]
                    print(f"  ✅ 产品视频裁剪: {os.path.basename(p_out)} ({clip_dur:.1f}s)")
                else:
                    raise Exception("ffmpeg输出文件不存在")
            except Exception as e:
                print(f"  [⚠️] 产品视频裁剪失败: {e}，使用原视频")
                p_out = p_path
                clip_dur = pair["product_duration"]

            product_shots.append({"type": "video", "path": p_out, "duration": clip_dur})

        # D. 处理穿衣服视频（骨架剪辑）
        print("\n[🦴] 处理穿衣展示视频（骨架剪辑）...")
        from providers.video.clip import ClipVideo
        clipper = ClipVideo()
        clothing_shots = []
        clothing_skeleton_sizes = []
        for pair in pairs:
            c_path = pair["clothing_path"]
            c_name = os.path.splitext(os.path.basename(c_path))[0]
            c_out = resolve_path(f"output/temp_clips/{c_name}_clothing_{datetime.now().strftime('%H%M%S')}.mp4")
            os.makedirs(os.path.dirname(c_out), exist_ok=True)

            try:
                clipped, avg_size = clipper.clip_video(c_path, c_out, target_duration=pair["clothing_duration"])
                clothing_skeleton_sizes.append(avg_size)
                # 获取实际剪辑后的时长
                import cv2
                cap = cv2.VideoCapture(clipped)
                c_fps = cap.get(cv2.CAP_PROP_FPS)
                c_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                c_dur = round(c_frames / c_fps, 1) if c_fps > 0 else pair["clothing_duration"]
                print(f"  ✅ 穿衣视频骨架剪辑: {os.path.basename(clipped)} ({c_dur}s, 骨架大小={avg_size:.0f})")
            except Exception as e:
                print(f"  [⚠️] 穿衣视频骨架分析失败: {e}，固定时长裁剪")
                c_out = c_path
                c_dur = pair["clothing_duration"]
                clothing_skeleton_sizes.append(0)

            clothing_shots.append({"type": "video", "path": c_out, "duration": c_dur})

        # E. 交替拼接：产品a + 穿衣a，产品b + 穿衣b ...
        print("\n[🔗] 交替拼接产品展示和穿衣展示...")
        shots = []
        for i, (p_shot, c_shot) in enumerate(zip(product_shots, clothing_shots)):
            shots.append(p_shot)  # 产品展示在前
            shots.append(c_shot)  # 穿衣展示在后
            print(f"  第{i+1}对: 产品展示({p_shot['duration']:.1f}s) + 穿衣展示({c_shot['duration']:.1f}s)")

        # 验证总时长
        total_actual = sum(s["duration"] for s in shots)
        print(f"\n  预计总时长: {total_actual:.1f}s")

        # 按骨架大小从小到大排序分镜（产品视频无骨架数据，size=0，自动排最前）
        all_sizes = [0] * len(product_shots) + clothing_skeleton_sizes
        if all_sizes and len(all_sizes) == len(shots):
            paired = list(zip(shots, all_sizes))
            paired.sort(key=lambda x: x[1])  # 按骨架大小升序
            shots = [p[0] for p in paired]
            print("  📐 分镜已按骨架大小从小到大排序（产品展示排前，穿衣按骨架大小排列）")

        # F. 视觉分析所有素材
        print("\n[👁️] 视觉分析所有素材...")
        from modules.vision_analyzer import analyze_all_materials
        vision_descriptions = analyze_all_materials(material_paths)
        for path, desc in vision_descriptions.items():
            print(f"  {os.path.basename(path)}: {desc}")
        self.cache["vision_descriptions"] = vision_descriptions

        # G. 从视觉分析推断主题，出文案（体现产品+穿衣交替结构）
        print("\n[✍️] 生成文案（带视觉上下文）...")
        vision_keywords = []
        for p, desc in vision_descriptions.items():
            short = desc[:40].strip()
            if short and not short.startswith("[视频素材"):
                vision_keywords.append(short)
        vision_hint = "；".join(vision_keywords[:3]) if vision_keywords else None
        topic = self._prompt_topic("素材关键词/主题", vision_hint=vision_hint)
        vision_context = "这是「产品+穿衣展示」交替剪辑的视频素材合集，标题要能覆盖整体内容。\n" + "\n".join([
            f"[{os.path.basename(p)}]: {desc}"
            for p, desc in vision_descriptions.items()
        ])
        copy_result = self.copy_engine.generate_copy(
            topic,
            material_context=format_analysis_for_prompt(self.cache.get("analysis", {})),
            visual_context=vision_context,
        )
        self.cache["copy"] = copy_result
        print(f"  标题: {copy_result['title']}")
        save_output(copy_result, topic)  # 📚 自动存入参考库

        # H. 进入配音→BGM→合成通用流程
        self._compose_video(shots, copy_result, vision_descriptions)

    def _handle_images_only(self, material_paths):
        """仅图片：视觉分析 → 出文案 → 生封面+卡片 → 输出图片路径"""
        # A. 视觉分析所有图片
        print("\n[👁️] 视觉分析所有图片素材...")
        from modules.vision_analyzer import analyze_all_materials
        vision_descriptions = analyze_all_materials(material_paths)
        for path, desc in vision_descriptions.items():
            print(f"  {os.path.basename(path)}: {desc}")
        self.cache["vision_descriptions"] = vision_descriptions

        # B. 从视觉分析推断主题，出文案
        print("\n[✍️] 生成文案（带视觉上下文）...")
        vision_hint = None
        for p, desc in vision_descriptions.items():
            short = desc[:40].strip()
            if short and not short.startswith("[图片素材") and not short.startswith("[视频素材"):
                vision_hint = short
                break
        topic = self._prompt_topic("素材关键词/主题", vision_hint=vision_hint)
        vision_context = "\n".join([
            f"[{os.path.basename(p)}]: {desc}"
            for p, desc in vision_descriptions.items()
        ])
        copy_result = self.copy_engine.generate_copy(
            topic,
            material_context=format_analysis_for_prompt(self.cache.get("analysis", {})),
            visual_context=vision_context,
        )
        self.cache["copy"] = copy_result
        print(f"  标题: {copy_result['title']}")
        print(f"  正文(预览): {copy_result['body'][:150]}...")
        save_output(copy_result, topic)  # 📚 自动存入参考库

        # C. 选择生成引擎 → 生封面+卡片
        engine = self._prompt_gen_engine("image")

        if engine == "jimeng":
            print("\n[🤖] 使用即梦AI生成封面...")
            from modules.jimeng_client import generate_image as jimeng_gen

            prompt = f"小红书封面，{copy_result['title']}，sleek modern design"
            result = jimeng_gen(prompt)
            if "urls" in result and result["urls"]:
                import requests
                from PIL import Image
                from io import BytesIO
                resp = requests.get(result["urls"][0], timeout=30)
                img = Image.open(BytesIO(resp.content))
                cover_path = resolve_path("output/images/jimeng_cover.png")
                os.makedirs(os.path.dirname(cover_path), exist_ok=True)
                img.save(cover_path)
                self.cache["cover"] = cover_path
                print(f"  ✅ 即梦封面: {cover_path}")
            else:
                print(f"  [⚠️] 即梦生图失败: {result.get('error', '未知错误')}，回退到脚本生成")
                self._generate_images(copy_result, material_paths)
        else:
            # 脚本生成（原逻辑）
            print("\n[🖼️] 生成封面和卡片（脚本生成）...")
            self._generate_images(copy_result, material_paths)

        # D. 输出图片路径
        print("\n✅ 图片已生成：")
        if self.cache.get("cover"):
            print(f"  📄 封面: {self.cache['cover']}")
        if self.cache.get("card"):
            print(f"  📄 卡片: {self.cache['card']}")
        if self.cache.get("stitch"):
            print(f"  📄 拼接图: {self.cache['stitch']}")

    def _handle_no_materials(self, topic, copy_result):
        """用户无素材时：先问图片还是视频 → 再针对性生成视觉内容"""
        print("\n" + "=" * 50)
        print("  🤖 全自动生成模式 — 无素材，脚本自产")
        print("=" * 50)

        body = copy_result.get("body", "")
        title = copy_result.get("title", "")

        # A. 把正文切成段落
        import re
        paragraphs = [p.strip() for p in re.split(r'[。！\n]', body) if len(p.strip()) > 10]
        key_points = paragraphs[:4]

        # B. 先问图片还是视频（不浪费资源先做决定）
        print("\n[❓] 请选择输出类型：")
        print("  1️⃣  图片 — 出封面+卡片")
        print("  2️⃣  视频 — 出分镜→配音→合成MP4（可另选即梦视频引擎）")
        choice = input("\n请选择 (1/2): ").strip()
        while choice not in ("1", "2"):
            print("  请输入 1（图片）或 2（视频）")
            choice = input("\n请选择 (1/2): ").strip()

        # C. 再问引擎选择（图片/视频共用）
        if choice == "2":
            engine = self._prompt_gen_engine("video")
        else:
            engine = self._prompt_gen_engine("image")

        generated = []

        if engine == "jimeng":
            # 即梦生成：封面 + 每张卡片
            print(f"\n[🤖] 使用即梦AI生成封面+{len(key_points)}张卡片...")
            from modules.jimeng_client import generate_image as jimeng_gen
            import requests
            from PIL import Image
            from io import BytesIO

            # 封面
            print("  [即梦] 生成封面...")
            result = jimeng_gen(f"小红书封面，{title}，sleek modern design")
            if "urls" in result and result["urls"]:
                resp = requests.get(result["urls"][0], timeout=30)
                img = Image.open(BytesIO(resp.content))
                cover_path = resolve_path("output/images/jimeng_cover.png")
                os.makedirs(os.path.dirname(cover_path), exist_ok=True)
                img.save(cover_path)
                generated.append(cover_path)
                print(f"  ✅ 即梦封面: {cover_path}")
            else:
                print(f"  [⚠️] 即梦封面失败: {result.get('error', '未知')}，回退脚本")
                from providers.image import get_provider as get_img_provider
                fallback = get_img_provider()
                cover = fallback.generate_cover(title=title, subtitle=topic, tags=copy_result.get("tags", [])[:4])
                generated.insert(0, cover)

            # 每张卡片用即梦
            for i, point in enumerate(key_points):
                short = point[:30] + "..." if len(point) > 30 else point
                print(f"  [即梦] 生成卡片{i+1}: {short}")
                result = jimeng_gen(f"信息卡片，{short}，clean design")
                if "urls" in result and result["urls"]:
                    resp = requests.get(result["urls"][0], timeout=30)
                    img = Image.open(BytesIO(resp.content))
                    card_path = resolve_path(f"output/images/jimeng_card_{i}.png")
                    img.save(card_path)
                    generated.append(card_path)
                    print(f"  ✅ 即梦卡片{i+1}: {card_path}")
                else:
                    print(f"  [⚠️] 即梦卡片{i+1}失败，跳过")

            if not generated:
                print("  [❌] 即梦全部失败，回退脚本")
                engine = "script"

        if engine != "jimeng" or not generated:
            # 脚本生成
            print(f"\n[🖼️] 脚本生成封面+{len(key_points)}张卡片...")
            from providers.image import get_provider as get_img_provider
            img_provider = get_img_provider()

            generated = []
            for i, point in enumerate(key_points):
                short = point[:30] + "..." if len(point) > 30 else point
                card = img_provider.generate_card(title=f"✨ {short}", subtitle=topic)
                generated.append(card)
                print(f"  ✅ 卡片{i+1}: {card}")

            cover = img_provider.generate_cover(title=title, subtitle=topic, tags=copy_result.get("tags", [])[:4])
            generated.insert(0, cover)

        self.cache["cover"] = generated[0]
        self.cache["material_paths"] = generated

        # D. 按之前的选择输出
        if choice == "1":
            print("\n✅ 已生成以下图片：")
            for p in generated:
                print(f"  📄 {p}")
        else:
            # 视频合成
            self._handle_multi_video(generated, [])

    def _generate_voiceover(self, copy_result, num_shots):
        """根据文案和分镜数量，生成每镜的配音文案"""
        body = copy_result.get("body", "")
        title = copy_result.get("title", "")

        sentences = [s.strip() for s in body.replace("。", "。\n").split("\n") if s.strip()]

        scripts = [title]
        remaining = [s for s in sentences if s]  # 过滤空字符串
        if num_shots > 1:
            per_shot = max(1, len(remaining) // (num_shots - 1))
            for i in range(num_shots - 1):
                chunk = remaining[:per_shot] if i < num_shots - 2 else remaining
                scripts.append("。".join(chunk))
                remaining = remaining[per_shot:]

        while len(scripts) < num_shots:
            scripts.append("")
        return scripts[:num_shots]

    def _generate_shot_voiceover(self, shots, copy_result, vision_descriptions):
        """
        根据每镜的画面描述 + 标题/正文，生成精准对应的配音文案

        Args:
            shots: [{"type": "image"|"video", "path": str, "duration": float}, ...]
            copy_result: {"title": str, "body": str, "tags": [...]}
            vision_descriptions: {path: description}

        Returns:
            list[str]: 每镜一句的配音文案
        """
        voice_script = []
        body = copy_result.get("body", "")
        title = copy_result.get("title", "")
        sentences = [s.strip() for s in body.replace("。", "。\n").split("\n") if s.strip()]

        # 每镜根据画面描述从正文匹配对应文案（不硬编码封面）
        remaining = list(sentences)
        for i, shot in enumerate(shots):
            desc = vision_descriptions.get(shot["path"], "")

            if desc and not desc.startswith("[视觉分析"):
                # 根据画面描述从正文找匹配句子
                matched = []
                # 尝试从正文找与画面描述相关的句子（简单关键词匹配）
                desc_keywords = set(desc.lower().split()[:5])
                scored = []
                for s in remaining:
                    s_lower = s.lower()
                    score = sum(1 for kw in desc_keywords if kw in s_lower)
                    scored.append((score, s))

                scored.sort(key=lambda x: -x[0])
                if scored and scored[0][0] > 0:
                    # 取最匹配的句子
                    matched.append(scored[0][1])
                    remaining.remove(scored[0][1])
                elif remaining:
                    # 没匹配到，取剩余第一条
                    matched.append(remaining.pop(0))

                voice_script.append("。".join(matched) if matched else desc)
            else:
                # 没有视觉描述，顺序分配正文句子
                if remaining:
                    voice_script.append(remaining.pop(0))
                else:
                    voice_script.append("")

        # 补齐不足的镜数
        while len(voice_script) < len(shots):
            voice_script.append("")

        return voice_script[:len(shots)]

    def _save_session(self, mode):
        """保存工作记录到参考库"""
        try:
            from utils.reference_reader import append

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            topic = self.cache.get("topic") or self.cache.get("copy", {}).get("title", "未知")
            record = (
                f"### 工作记录: {topic}\n"
                f"- 模式: {'素材驱动' if mode == 'material_driven' else '主题驱动'}\n"
                f"- 时间: {timestamp}\n"
                f"- 标题: {self.cache.get('copy', {}).get('title', '')}\n"
                f"- 标签: {', '.join(self.cache.get('copy', {}).get('tags', []))}\n"
            )
            append("历史帖子", record)
            print("\n[📚] 工作记录已保存到参考库")

            # ── 追加用户偏好记录 ──
            try:
                import yaml

                prefs_path = resolve_path("references/用户偏好.yaml")

                # 确定 BGM 相关信息
                bgm_path = self.cache.get("bgm_path")
                bgm_filename = os.path.basename(bgm_path) if bgm_path else None

                # 判断 BGM 来源
                bgm_source = None
                if bgm_path:
                    bgm_library = resolve_path("references/bgm_library/")
                    if os.path.exists(bgm_library) and bgm_path.startswith(bgm_library):
                        bgm_source = "library"
                    else:
                        bgm_source = "user_provided"

                # 配音信息
                voiceover_path = self.cache.get("voiceover_path")
                has_voiceover = bool(voiceover_path)
                voice_script = self.cache.get("voice_script", [])

                # shots / 总时长
                shots = self.cache.get("shots", [])
                total_duration = self.cache.get("total_duration", 0.0)

                prefs_entry = {
                    "timestamp": timestamp,
                    "mode": mode,
                    "title": self.cache.get("copy", {}).get("title", ""),
                    "tags": self.cache.get("copy", {}).get("tags", []),
                    "total_duration": round(total_duration, 1),
                    "shots": len(shots),
                    "bgm": bgm_filename,
                    "bgm_source": bgm_source,
                    "voiceover_script_len": len(voice_script),
                    "has_voiceover": has_voiceover,
                }

                # 读取已有记录，追加
                if os.path.exists(prefs_path):
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 只取 YAML 数据部分（跳过注释头）
                    data = yaml.safe_load(content) or []
                else:
                    data = []

                if not isinstance(data, list):
                    data = []

                data.append(prefs_entry)

                # 写回（保留注释头 + YAML 数据）
                header = (
                    "# ============================================================\n"
                    "# 用户偏好记录\n"
                    "# 每次完成一个成品后自动追加，用于学习用户创作习惯\n"
                    "# ============================================================\n"
                )
                with open(prefs_path, "w", encoding="utf-8") as f:
                    f.write(header)
                    yaml.dump(data, f, allow_unicode=True, indent=2, sort_keys=False,
                               default_flow_style=False)

                print(f"[📊] 用户偏好已记录到 {os.path.basename(prefs_path)}")
            except Exception as e2:
                print(f"\n[⚠️] 保存用户偏好失败: {e2}")

        except Exception as e:
            print(f"\n[⚠️] 保存工作记录失败: {e}")

    # ============================================================
    # 模式三：全自动量产
    # ============================================================

    def mode_auto_full(self):
        """
        模式三：全自动量产
        6个穿搭视频 → 骨架剪辑 → Kimi分析 → 文案 → 漫威开头 → BGM合成 → 输出
        素材硬编码在 E:/任务/小红书内容工坊/materials/ 下
        """
        print("=" * 60)
        print("  📦 模式三：全自动量产")
        print("  主题: 六种穿搭 六套衣服种草")
        print("  素材: E:\\任务\\小红书内容工坊\\materials\\")
        print("=" * 60)

        MATERIALS_DIR = r"E:\任务\小红书内容工坊\materials"
        video_files = [
            "video1_18-14.mp4", "video2_18-15a.mp4", "video3_18-15b.mp4",
            "video4_18-15c.mp4", "video5_18-16a.mp4", "video6_18-16b.mp4",
        ]
        material_paths = [os.path.join(MATERIALS_DIR, f) for f in video_files]

        # ===== 1. 骨架分析 + 剪辑 =====
        print("\n[1/6] 骨架分析 + 视频剪辑...")
        total_dur = 45
        per_video_dur = total_dur / len(video_files)
        from providers.video.clip import ClipVideo
        clipper = ClipVideo()

        shots = []
        skeleton_sizes = []
        for v_path in material_paths:
            v_name = os.path.splitext(os.path.basename(v_path))[0]
            v_out = resolve_path(f"output/temp_clips/{v_name}_clip.mp4")
            os.makedirs(os.path.dirname(v_out), exist_ok=True)
            try:
                clipped, avg_size = clipper.clip_video(v_path, v_out, target_duration=per_video_dur)
                skeleton_sizes.append(avg_size)
                import cv2
                cap = cv2.VideoCapture(clipped)
                v_fps = cap.get(cv2.CAP_PROP_FPS)
                v_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.release()
                v_dur = round(v_frames / v_fps, 1) if v_fps > 0 else 5.0
                shots.append({"type": "video", "path": clipped, "duration": v_dur})
                print(f"  ✅ {v_name}: {v_dur}s (骨架大小={avg_size:.0f})")
            except Exception as e:
                print(f"  [⚠️] {v_name} 失败: {e}")
                shots.append({"type": "video", "path": v_path, "duration": round(per_video_dur, 1)})
                skeleton_sizes.append(0)

        # ===== 2. Kimi视觉分析 =====
        print("\n[2/6] Kimi视觉分析...")
        from modules.vision_analyzer import analyze_all_materials
        vision_descriptions = analyze_all_materials(material_paths)
        for path, desc in vision_descriptions.items():
            print(f"  {os.path.basename(path)}: {desc[:60]}...")

        # ===== 3. 生成文案 =====
        print("\n[3/6] 生成文案...")
        vision_keywords = []
        for p, desc in vision_descriptions.items():
            short = desc[:40].strip()
            if short and not short.startswith("[视频素材"):
                vision_keywords.append(short)
        vision_hint = "；".join(vision_keywords[:3]) if vision_keywords else None
        vision_context = "这是多段视频素材合集，标题要能覆盖整体内容。\n" + "\n".join([
            f"[{os.path.basename(p)}]: {desc}" for p, desc in vision_descriptions.items()
        ])

        # 模拟主程序的引擎初始化
        from providers.copy import get_provider as get_copy_provider
        copy_engine = get_copy_provider()

        copy_result = copy_engine.generate(
            "六种穿搭 六套衣服种草",
            context=vision_context,
        )
        print(f"  标题: {copy_result['title']}")
        print(f"  正文: {copy_result.get('body', '')[:100]}...")

        # ===== 4. 按骨架大小排序分镜 =====
        print("\n[4/6] 分镜排序...")
        if skeleton_sizes and len(skeleton_sizes) == len(shots):
            paired = list(zip(shots, skeleton_sizes))
            paired.sort(key=lambda x: x[1])
            shots = [p[0] for p in paired]
            print("  ✅ 已按骨架大小从小到大排序")

        # ===== 5. 生成漫威开头 =====
        print("\n[5/6] 生成漫威风格混剪开头...")
        from providers.video.clip import ClipVideo
        clipper2 = ClipVideo()

        # 从剪辑好的片段里抽帧（不是原始素材），保证图片和视频画面一致
        clip_paths = [s["path"] for s in shots if os.path.isfile(s["path"])]

        per_video_frames = []
        for clip_path in clip_paths:
            try:
                frames = clipper2.extract_good_frames(clip_path, max_frames=15, consistent_pose=True)
                per_video_frames.append(frames)
            except Exception:
                pass

        all_frames = []
        if per_video_frames:
            max_per = max(len(f) for f in per_video_frames)
            for i in range(max_per):
                for vf in per_video_frames:
                    if i < len(vf):
                        all_frames.append(vf[i])
            print(f"  ✅ 从剪辑片段提取 {len(all_frames)} 张好帧（{len(per_video_frames)}个片段穿插）")

        # 九宫格：也从剪辑片段里截取
        import random, subprocess, cv2
        grid_clips = []
        grid_temp_dir = resolve_path("output/temp_clips/")
        os.makedirs(grid_temp_dir, exist_ok=True)
        grid_videos = clip_paths[:]
        random.shuffle(grid_videos)

        for i in range(9):
            v_path = grid_videos[i % len(grid_videos)]
            try:
                cap = cv2.VideoCapture(v_path)
                total_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps_v = cap.get(cv2.CAP_PROP_FPS) or 30
                cap.release()
                v_dur = total_f / fps_v if fps_v > 0 else 60
                start_sec = random.uniform(1, max(2, v_dur - 5)) if v_dur > 5 else 0.5
                clip_out = os.path.join(grid_temp_dir, f"grid_{i+1:02d}.mp4")
                subprocess.run(["ffmpeg", "-i", v_path, "-ss", str(start_sec),
                    "-t", "7.5", "-c:v", "libx264", "-c:a", "aac", "-y", clip_out
                ], capture_output=True, timeout=30)
                if os.path.exists(clip_out) and os.path.getsize(clip_out) > 0:
                    grid_clips.append(clip_out)
            except Exception:
                continue
        print(f"  ✅ 九宫格片段: {len(grid_clips)}/9")

        # 合成开头
        from modules.video_composer import create_marvel_intro
        import re
        title_en = copy_result.get("title", "FASHION SHOW")
        eng_words = re.findall(r'[A-Za-z]+', title_en)
        title_en = " ".join(eng_words[:5]).upper() if eng_words else "FASHION SHOW"
        print(f"  标题英文: {title_en}")

        from datetime import datetime
        intro_path = resolve_path(f"output/temp_clips/intro_{datetime.now().strftime('%H%M%S')}.mp4")
        create_marvel_intro(
            shot_images=all_frames if all_frames else [],
            grid_clips=grid_clips,
            title_text=title_en,
            output_path=intro_path,
            resolution=(1080, 1920),
            fps=30,
            duration=7.0,
        )

        # 插入第一镜（不加BGM，让compose_mixed统一处理）
        shots.insert(0, {"type": "video", "path": intro_path, "duration": 7.0})

        # ===== 6. 合成最终视频（带BGM，统一处理所有片段） =====
        print("\n[6/6] 合成最终视频...")
        bgm_path = resolve_path("references/bgm_library/upbeat_bgm.mp3")
        final_out = resolve_path(f"output/videos/六种穿搭_{datetime.now().strftime('%H%M%S')}.mp4")
        from modules.video_composer import compose_mixed
        final = compose_mixed(
            shots=shots,
            output_path=final_out,
            bgm_path=bgm_path,
            resolution=(1080, 1920),
        )
        total_len = sum(s["duration"] for s in shots)
        size_mb = os.path.getsize(final) / 1024 / 1024
        print(f"\n✅ 最终视频: {final}")
        print(f"  总时长: {total_len:.0f}s")
        print(f"  大小: {size_mb:.1f}MB")
        print("✅ 全流程完成！")

        self.cache["video"] = final
        return self.cache


# ============================================================
# 入口
# ============================================================

def main():
    """主入口"""
    workshop = XHSWorkshop()

    print("\n请选择工作模式：")
    print("  1️⃣  模式一：素材驱动 — 你有素材，帮你出文案出片")
    print("  2️⃣  模式二：主题驱动 — 有个想法，搜素材做规划出片")
    print("  3️⃣  模块测试 — 单独测试各模块")
    print("  4️⃣  模式三：全自动量产 — 6个穿搭视频一键出片")

    choice = input("\n请选择 (1/2/3/4): ").strip()

    if choice == "1":
        workshop.mode_material_driven()
    elif choice == "2":
        workshop.mode_topic_driven()
    elif choice == "3":
        run_module_tests()
    elif choice == "4":
        workshop.mode_auto_full()
    else:
        print("[❌] 无效选择，使用模式一")
        workshop.mode_material_driven()


def run_module_tests():
    """运行所有模块测试"""
    print("\n" + "=" * 50)
    print("  🧪 模块测试")
    print("=" * 50)

    print("\n1. 配置加载测试")
    from utils import config_loader
    config_loader.load_config()
    print("   ✓ config.yaml 加载成功")

    print("\n2. 参考库测试")
    from utils import reference_reader
    refs = reference_reader.read_all()
    print(f"   ✓ 读取 {len(refs)} 个参考库文件")
    for name in refs:
        print(f"      - {name}")

    print("\n3. 文案引擎测试")
    from modules import copy_engine
    engine = copy_engine.CopyEngine()
    titles = engine.generate_title("开源效率工具")
    print(f"   ✓ 生成了 {len(titles)} 个标题")

    print("\n4. 本地生图测试")
    from modules import local_image
    path = local_image.generate_card("测试标题", "测试副标题", bg_color="#1A1A2E")
    print(f"   ✓ 卡片生成: {path}")

    print("\n5. 素材分析测试")
    from modules import 素材分析
    test_paths = ["E:/任务/小红书内容工坊/output/test_materials"]
    if os.path.isdir(test_paths[0]):
        analysis = 素材分析.analyze_materials(test_paths[0])
        print(f"   ✓ 分析结果: {analysis['summary']}")

    print("\n6. MoviePy视频合成测试")
    from modules import video_composer
    print(f"   ✓ MoviePy 可用: {video_composer.MOVIEPY_AVAILABLE}")

    print("\n7. 搜索模块测试")
    from modules import search
    searcher = search.SearXNGSearch()
    print("   ✓ SearXNG 已初始化")

    print("\n8. 模板测试")
    from templates import cover_template, card_template
    print(f"   ✓ 封面模板: {list(cover_template.TEMPLATES.keys())}")
    print(f"   ✓ 卡片模板: {list(card_template.CARD_TEMPLATES.keys())}")

    print("\n" + "=" * 50)
    print("  ✅ 所有模块测试通过！")
    print("=" * 50)


if __name__ == "__main__":
    main()
