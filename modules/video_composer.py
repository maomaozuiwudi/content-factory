"""
视频合成模块 — MoviePy 引擎
替代剪映，直接输出MP4

支持：
- 图片/视频混排
- 掐头去尾、剪掉中间片段
- 转场效果（淡入淡出/滑动/百叶窗等）
- 多轨道合成（画中画/分屏）
- 配音 + BGM混音

依赖 providers/video/ 插槽层动态切换后端。
"""

import os, json, subprocess, asyncio
from pathlib import Path

from providers.video import get_provider
from providers.video.moviepy import MOVIEPY_AVAILABLE


# 全局单例 provider
_provider = None


def _get_provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider


def make_slideshow(image_paths, output_path, duration_per_image=4.0,
                   transition_duration=0.5, transition_type="fade",
                   resolution=(1920, 1080), fps=30):
    """图片列表 → 幻灯片视频 — 委托给 provider"""
    return _get_provider().make_slideshow(
        image_paths, output_path, duration_per_image,
        transition_duration, transition_type, resolution, fps
    )


def concat_videos(video_paths, output_path, cuts=None, transitions=None,
                  resolution=(1920, 1080), fps=30):
    """视频列表 → 拼接 — 委托给 provider"""
    return _get_provider().concat_videos(
        video_paths, output_path, cuts, transitions, resolution, fps
    )


def add_audio(video_path, voiceover_path=None, bgm_path=None,
              output_path=None, voice_volume=1.0, bgm_volume=0.15):
    """给视频添加配音和BGM — 委托给 provider"""
    return _get_provider().add_audio(
        video_path, voiceover_path, bgm_path,
        output_path, voice_volume, bgm_volume
    )


def images_to_video(image_paths, output_path, voiceover_scripts=None,
                    voiceover_path=None,
                    bgm_path=None, duration_per_image=4.0,
                    transition_duration=0.5, resolution=(1920, 1080),
                    fps=30, tts_voice="zh-CN-XiaoxiaoNeural"):
    """图片 → 最终成品MP4 一条龙 — 委托给 provider"""
    return _get_provider().images_to_video(
        image_paths, output_path, voiceover_scripts, voiceover_path, bgm_path,
        duration_per_image, transition_duration, resolution,
        fps, tts_voice
    )


def compose_mixed(shots, output_path, voiceover_path=None, bgm_path=None,
                  resolution=(1920, 1080), fps=30):
    """
    混合合成：图片→ImageClip + 视频→VideoFileClip 混合拼接

    Args:
        shots: [{"type": "image"|"video", "path": str, "duration": float}, ...]
        output_path: 输出MP4
        voiceover_path: 外部配音音频（可选）
        bgm_path: 背景音乐（可选）
        resolution: (宽, 高)，默认 1920x1080
        fps: 帧率，默认30
    """
    from moviepy import (
        ImageClip, VideoFileClip, AudioFileClip,
        concatenate_videoclips, CompositeAudioClip,
        vfx, afx,
    )

    # 前置校验：每个shot的必填字段
    for i, s in enumerate(shots):
        if not isinstance(s, dict):
            raise ValueError(f"shots[{i}] 不是字典: {s}")
        if "type" not in s or "path" not in s or "duration" not in s:
            raise ValueError(f"shots[{i}] 缺少必填字段 (type/path/duration): {s}")
        if s["type"] not in ("image", "video"):
            raise ValueError(f"shots[{i}] type 必须为 image 或 video，得到: {s['type']}")
        if not isinstance(s["duration"], (int, float)) or s["duration"] <= 0:
            raise ValueError(f"shots[{i}] duration 必须为正数，得到: {s['duration']}")
        if not os.path.isfile(s["path"]):
            raise ValueError(f"shots[{i}] 文件不存在或不可读: {s['path']}")

    clips = []
    final = None
    try:
        for s in shots:
            if s["type"] == "image":
                clip = ImageClip(s["path"]).with_duration(s["duration"])
                # 缩放适配目标分辨率
                clip = clip.resized(width=resolution[0])
                if clip.h < resolution[1]:
                    clip = clip.resized(height=resolution[1])
                clip = clip.with_effects([vfx.Resize((resolution[0], resolution[1]))])
            else:
                clip = VideoFileClip(s["path"])
                # 缩放适配目标分辨率（视频片段可能来自骨架剪辑，分辨率不同）
                clip = clip.resized(width=resolution[0])
                if clip.h < resolution[1]:
                    clip = clip.resized(height=resolution[1])
                clip = clip.with_effects([vfx.Resize((resolution[0], resolution[1]))])
                # 取实际时长和设定时长的较小值，短了就 loop 避免冻结
                actual_dur = min(clip.duration, s["duration"])
                if clip.duration > actual_dur:
                    clip = clip.subclipped(0, actual_dur)
                elif clip.duration < actual_dur:
                    clip = clip.with_effects([vfx.Loop(duration=actual_dur)])
            clips.append(clip)

        final = concatenate_videoclips(clips, method="chain")
        video_duration = final.duration  # 记住视频实际时长

        # 加音频
        audio_tracks = []
        try:
            if voiceover_path and os.path.isfile(voiceover_path):
                voice = AudioFileClip(voiceover_path).with_effects([afx.MultiplyVolume(1.0)])
                # 配音截到视频时长，避免 MoviePy 自动扩展最后一帧
                if voice.duration > video_duration:
                    voice = voice.subclipped(0, video_duration)
                audio_tracks.append(voice)
            if bgm_path and os.path.isfile(bgm_path):
                try:
                    bgm = AudioFileClip(bgm_path)
                    # 保护：BGM太短（<1秒）或文件太小可能损坏，跳过
                    if bgm.duration < 1.0:
                        print(f"  [⚠️] BGM太短 ({bgm.duration:.1f}s)，跳过")
                        bgm.close()
                        bgm = None
                    else:
                        if bgm.duration < video_duration:
                            bgm = bgm.loop(duration=video_duration)
                        else:
                            bgm = bgm.subclipped(0, video_duration)
                        bgm = bgm.with_effects([afx.MultiplyVolume(0.15)])
                        audio_tracks.append(bgm)
                except Exception as e:
                    print(f"  [⚠️] BGM加载失败: {e}，跳过BGM")
                    try:
                        if 'bgm' in dir() and bgm is not None:
                            bgm.close()
                    except Exception:
                        pass

            if audio_tracks:
                final_audio = CompositeAudioClip(audio_tracks)
                final = final.with_audio(final_audio)
            # 显式限制视频时长，防止 with_audio 自动扩展
            final = final.subclipped(0, video_duration)

            final.write_videofile(output_path, codec="libx264", audio_codec="aac",
                                  preset="medium", bitrate="5000k", threads=2, logger=None)
        finally:
            for a in audio_tracks:
                try:
                    a.close()
                except Exception:
                    pass
    finally:
        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass
        if final is not None:
            try:
                final.close()
            except Exception:
                pass
    return output_path


def create_marvel_intro(shot_images, grid_clips, title_text, output_path,
                        resolution=(1080, 1920), fps=30, duration=4.0):
    """创建漫威风格混剪开头

    左侧40%：图片超快切（0.05-0.1秒/张）
    右侧60%：九宫格视频展示（9个短片段同时播放）
    左侧图片区叠加镂空文字（透过文字看到背后快切的图片）

    Args:
        shot_images: 超快切图片路径列表（左侧）
        grid_clips: 九宫格视频片段路径列表（右侧，需9个）
        title_text: 镂空文字内容（标题英文）
        output_path: 输出MP4路径
        resolution: 分辨率 (宽, 高)，默认 (1080, 1920)
        fps: 帧率，默认30
        duration: 开头总时长（秒），默认4.0

    Returns:
        str: 输出路径
    """
    from moviepy import (
        ImageClip, VideoFileClip, TextClip,
        CompositeVideoClip, concatenate_videoclips,
        vfx,
    )

    def _find_font():
        """Helper: find a usable font path on this system.
        Prioritize Chinese-capable fonts for titles like "周宝宝".
        """
        candidates = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/yahei.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return "Arial"  # fallback

    try:
        import numpy as np
    except ImportError:
        np = None

    w, h = resolution
    left_w = int(w * 0.48)
    right_w = w - left_w
    grid_rows, grid_cols = 3, 3
    cell_w = right_w // grid_cols
    cell_h = h // grid_rows

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    print(f"[create_marvel_intro] 创建漫威风格开头: {duration}s")
    print(f"  左侧快切: {len(shot_images)} 张图片")
    print(f"  右侧九宫格: {len(grid_clips)} 个视频")
    print(f"  文字: {title_text}")
    print(f"  分辨率: {resolution}, 帧率: {fps}")

    # ── 左侧：图片超快切 ──────────────────────────────────────
    left_clip = None
    if shot_images:
        # 每张图的显示时间
        t_per_image = duration / len(shot_images)
        img_clips = []
        for img_path in shot_images:
            try:
                img_clip = (ImageClip(img_path)
                            .resized(width=left_w)        # 按宽度缩放
                            .with_position((0, "center"))  # 垂直居中
                            .with_duration(t_per_image))
                # 裁剪高度到 h
                if img_clip.h > h:
                    # 居中裁剪
                    center_y = img_clip.h // 2
                    img_clip = img_clip.cropped(
                        x1=0, y1=center_y - h // 2,
                        x2=left_w, y2=center_y + h // 2
                    )
                elif img_clip.h < h:
                    # 高度不够就按高度缩放并重新居中裁剪宽度
                    img_clip = (ImageClip(img_path)
                                .resized(height=h)
                                .with_position((0, 0))
                                .with_duration(t_per_image))
                    if img_clip.w > left_w:
                        center_x = img_clip.w // 2
                        img_clip = img_clip.cropped(
                            x1=max(0, center_x - left_w // 2), y1=0,
                            x2=min(img_clip.w, center_x + left_w // 2), y2=h
                        )
                    else:
                        img_clip = (ImageClip(img_path)
                                    .resized(width=left_w)
                                    .with_position((0, "center"))
                                    .with_duration(t_per_image))
                img_clips.append(img_clip)
            except Exception as e:
                print(f"  [⚠️] 跳过图片 {img_path}: {e}")

        if img_clips:
            left_clip = concatenate_videoclips(img_clips, method="chain")
            # 保底时长
            if left_clip.duration < duration:
                extra = duration - left_clip.duration
                last_img = img_clips[-1].with_duration(img_clips[-1].duration + extra)
                img_clips[-1] = last_img
                left_clip = concatenate_videoclips(img_clips, method="chain")
        else:
            # 无图片时用黑屏
            left_clip = ImageClip(
                np.full((h, left_w, 3), 20, dtype=np.uint8) if np else None,
                duration=duration
            )

    # 确保 left_clip 时长正确
    if left_clip is None:
        left_clip = ImageClip(
            np.full((h, left_w, 3), 20, dtype=np.uint8) if np else None,
            duration=duration
        )

    # ── 右侧：九宫格视频 ──────────────────────────────────────
    right_clips = []
    # 如果不足9个，循环复用
    expanded_clips = []
    if grid_clips:
        for i in range(9):
            expanded_clips.append(grid_clips[i % len(grid_clips)])

    for i, clip_path in enumerate(expanded_clips):
        row = i // grid_cols
        col = i % grid_cols
        x_pos = left_w + col * cell_w
        y_pos = row * cell_h

        try:
            v_clip = VideoFileClip(clip_path, audio=False)
            # 取实际时长和duration的较小值
            actual_dur = min(v_clip.duration, duration)
            if v_clip.duration > actual_dur:
                v_clip = v_clip.subclipped(0, actual_dur)

            # 等比例缩放铺满格子，多余裁切
            v_w, v_h = v_clip.size
            scale_ratio = max(cell_w / v_w, cell_h / v_h)
            new_w = int(v_w * scale_ratio)
            new_h = int(v_h * scale_ratio)
            v_clip = v_clip.resized(width=new_w, height=new_h)

            # 居中裁剪到格子大小
            cx, cy = new_w // 2, new_h // 2
            x1 = max(0, cx - cell_w // 2)
            y1 = max(0, cy - cell_h // 2)
            v_clip = v_clip.cropped(
                x1=x1, y1=y1,
                x2=min(new_w, x1 + cell_w),
                y2=min(new_h, y1 + cell_h)
            )
            v_clip = v_clip.with_position((x_pos, y_pos))

            # 用Loop循环播放填充到目标时长
            if v_clip.duration < duration:
                from moviepy import vfx
                v_clip = v_clip.with_effects([vfx.Loop(duration=duration)])
            else:
                v_clip = v_clip.with_duration(duration)

            right_clips.append(v_clip)
        except Exception as e:
            print(f"  [⚠️] 跳过九宫格视频 {clip_path}: {e}")
            # 用黑底填充
            black = ImageClip(
                np.full((cell_h, cell_w, 3), 10, dtype=np.uint8) if np else None,
                duration=duration
            ).with_position((x_pos, y_pos))
            right_clips.append(black)

    # ── 合成左右两侧 ──────────────────────────────────────────
    all_clips = [left_clip] + right_clips
    base = CompositeVideoClip(all_clips, size=(w, h))

    # ── 左侧镂空文字效果（英文竖排大号，纯镂空无描边） ──────
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # 3个单词竖排：ZHOU, BAO, BAO（放大3倍）
        vertical_text = "ZHOU\nBAO\nBAO"
        font_path = _find_font()
        font_size = int(left_w * 0.39)  # 放大3倍 ≈ 202px
        pil_font = ImageFont.truetype(font_path, font_size)
        
        lines = vertical_text.split('\n')
        char_heights = []
        max_char_w = 0
        for line in lines:
            bbox = pil_font.getbbox(line)
            cw = bbox[2] - bbox[0]
            ch = bbox[3] - bbox[1]
            max_char_w = max(max_char_w, cw)
            char_heights.append(ch + int(font_size * 0.12))
        
        total_text_h = sum(char_heights)
        start_y = max(10, (h - total_text_h) // 2)
        
        # 创建镂空遮罩（灰色=半透明背景，黑色=文字区域完全透明）
        mask_img = Image.new('L', (left_w, h), 180)
        draw = ImageDraw.Draw(mask_img)
        current_y = start_y
        for i, line in enumerate(lines):
            bbox = pil_font.getbbox(line)
            lw = bbox[2] - bbox[0]
            lx = (left_w - lw) // 2
            draw.text((lx, current_y), line, font=pil_font, fill=0)
            current_y += char_heights[i]
        
        # 纯镂空遮罩层（无白色描边，文字区域直接显示背后的快切图片）
        overlay_array = np.full((h, left_w, 3), (0, 0, 0), dtype=np.uint8)
        mask_np = np.array(mask_img)
        overlay_clip = ImageClip(overlay_array, duration=duration)
        overlay_clip = overlay_clip.with_mask(ImageClip(mask_np, is_mask=True, duration=duration))
        overlay_clip = overlay_clip.with_position((0, 0))
        
        base = CompositeVideoClip([base, overlay_clip], size=(w, h))
        print("  [✅] 镂空效果: 竖排英文 ZHOU BAO BAO (3x大, 纯镂空)")
    except Exception as e:
        print(f"  [⚠️] 镂空文字创建失败: {e}")
        import traceback; traceback.print_exc()

    # ── 写入文件 ──────────────────────────────────────────────
    print(f"[create_marvel_intro] 渲染输出: {output_path}")
    base.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=fps,
        preset="medium",
        bitrate="5000k",
        threads=2,
        logger=None,
    )

    # 清理
    try:
        base.close()
        left_clip.close()
        for c in right_clips:
            try:
                c.close()
            except Exception:
                pass
        if img_clips:
            for c in img_clips:
                try:
                    c.close()
                except Exception:
                    pass
    except Exception:
        pass

    print(f"[create_marvel_intro] ✅ 漫威风格开头已生成: {output_path}")
    return output_path


# 快速测试
if __name__ == "__main__":
    from providers.video.moviepy import MOVIEPY_AVAILABLE
    print(f"MoviePy 可用: {MOVIEPY_AVAILABLE}")
    print("请通过内容工坊主程序调用，或直接使用 images_to_video()")
