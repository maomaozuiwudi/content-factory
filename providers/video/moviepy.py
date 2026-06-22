"""
MoviePy 视频合成 Provider

从 modules/video_composer.py 迁移而来，保持原有行为不变。
"""

import os
import json
import subprocess
import asyncio

try:
    from moviepy import (
        VideoFileClip, ImageClip, AudioFileClip,
        CompositeVideoClip, concatenate_videoclips,
        vfx, afx, TextClip, CompositeAudioClip,
    )
    MOVIEPY_AVAILABLE = True
except ImportError:
    print("[⚠️] moviepy 未安装，请手动安装：pip install moviepy")
    MOVIEPY_AVAILABLE = False


def _check_available():
    """检查 MoviePy 是否可用，不可用时抛出 RuntimeError"""
    if not MOVIEPY_AVAILABLE:
        raise RuntimeError("MoviePy 不可用，请安装: pip install moviepy")


def _normalize_path(path):
    """规范化路径，防止路径穿越"""
    if path is None:
        return None
    return os.path.normpath(path)


class MoviePyVideo:
    """MoviePy 驱动的视频合成器"""

    def compose(self, image_paths, text="", output_path="output.mp4",
                duration_per_image=4.0, resolution=(1920, 1080)):
        """图片 → 配音 → BGM → MP4，一条龙出片

        Args:
            image_paths: 图片路径列表
            text: 配音文案
            output_path: 输出MP4路径
            duration_per_image: 每张图时长（秒）
            resolution: (宽, 高)

        Returns:
            str: MP4路径
        """
        _check_available()
        output_path = _normalize_path(output_path)
        return self.images_to_video(
            image_paths=image_paths,
            output_path=output_path,
            voiceover_scripts=[text] if text else None,
            duration_per_image=duration_per_image,
            resolution=resolution,
        )

    def make_slideshow(self, image_paths, output_path, duration_per_image=4.0,
                       transition_duration=0.5, transition_type="fade",
                       resolution=(1920, 1080), fps=30):
        """图片列表 → 幻灯片视频（带转场）"""
        _check_available()
        output_path = _normalize_path(output_path)
        print(f"[🎬 MoviePy] 生成幻灯片: {len(image_paths)}张图")

        clips = []
        try:
            for i, img_path in enumerate(image_paths):
                img_path = _normalize_path(img_path)
                if not os.path.isfile(img_path):
                    print(f"  [⚠️] 跳过不存在的文件: {img_path}")
                    continue

                clip = (ImageClip(img_path)
                        .with_duration(duration_per_image)
                        .resized(width=resolution[0]))

                if clip.h < resolution[1]:
                    clip = (ImageClip(img_path)
                            .with_duration(duration_per_image)
                            .resized(height=resolution[1]))

                clip = clip.cropped(x_center=clip.w / 2, y_center=clip.h / 2,
                                    width=resolution[0], height=resolution[1])

                if i > 0 and transition_type == "fade":
                    clip = clip.with_effects([vfx.FadeIn(transition_duration)])
                elif transition_type == "slide":
                    clip = clip.resized(lambda t: 1 + 0.05 * (t / duration_per_image))

                clips.append(clip)

            if not clips:
                raise ValueError("没有有效的图片素材")

            if len(clips) == 1:
                final = clips[0]
            else:
                final = concatenate_videoclips(clips, method="compose", padding=-transition_duration)

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            final.write_videofile(output_path, codec="libx264", audio_codec="aac",
                                  fps=fps, preset="medium", bitrate="5000k",
                                  threads=2, logger=None)
            final.close()
            print(f"  ✅ 输出: {output_path}")
        finally:
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass
        return output_path

    def concat_videos(self, video_paths, output_path, cuts=None, transitions=None,
                      resolution=(1920, 1080), fps=30):
        """视频列表 → 拼接，支持裁剪和转场"""
        _check_available()
        output_path = _normalize_path(output_path)
        print(f"[🎬 MoviePy] 拼接视频: {len(video_paths)}段")

        clips = []
        try:
            for i, vpath in enumerate(video_paths):
                vpath = _normalize_path(vpath)
                if not os.path.isfile(vpath):
                    print(f"  [⚠️] 跳过: {vpath}")
                    continue

                clip = VideoFileClip(vpath)

                if cuts and i < len(cuts) and cuts[i]:
                    start, end = cuts[i]
                    clip = clip.subclipped(start, end)

                if clip.w != resolution[0] or clip.h != resolution[1]:
                    clip = clip.resized(width=resolution[0], height=resolution[1])

                clips.append(clip)

            if not clips:
                raise ValueError("没有有效视频")

            final = concatenate_videoclips(clips, method="compose")
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            final.write_videofile(output_path, codec="libx264", audio_codec="aac",
                                  fps=fps, preset="medium", bitrate="5000k",
                                  threads=2, logger=None)
            final.close()
            print(f"  ✅ 输出: {output_path}")
        finally:
            for clip in clips:
                try:
                    clip.close()
                except Exception:
                    pass
        return output_path

    def add_audio(self, video_path, voiceover_path=None, bgm_path=None,
                  output_path=None, voice_volume=1.0, bgm_volume=0.15):
        """给视频添加配音和背景音乐"""
        _check_available()
        video_path = _normalize_path(video_path)
        output_path = _normalize_path(output_path)
        if voiceover_path:
            voiceover_path = _normalize_path(voiceover_path)
        if bgm_path:
            bgm_path = _normalize_path(bgm_path)

        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        if output_path is None:
            output_path = video_path.replace(".mp4", "_audio.mp4")

        print(f"[🎵 MoviePy] 添加音频: 配音={voiceover_path is not None}, BGM={bgm_path is not None}")

        video = None
        audio_tracks = []
        try:
            video = VideoFileClip(video_path)

            if voiceover_path and os.path.isfile(voiceover_path):
                voice = AudioFileClip(voiceover_path).with_effects([afx.MultiplyVolume(voice_volume)])
                audio_tracks.append(voice)

            if bgm_path and os.path.isfile(bgm_path):
                bgm = AudioFileClip(bgm_path)
                if bgm.duration < video.duration:
                    bgm = bgm.loop(duration=video.duration)
                else:
                    bgm = bgm.subclipped(0, video.duration)
                bgm = bgm.with_effects([afx.MultiplyVolume(bgm_volume)])
                audio_tracks.append(bgm)

            if audio_tracks:
                final_audio = CompositeAudioClip(audio_tracks)
                video = video.with_audio(final_audio)

            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            video.write_videofile(output_path, codec="libx264", audio_codec="aac",
                                  preset="medium", bitrate="5000k",
                                  threads=2, logger=None)
            print(f"  ✅ 输出: {output_path}")
        finally:
            if video is not None:
                try:
                    video.close()
                except Exception:
                    pass
            for a in audio_tracks:
                try:
                    a.close()
                except Exception:
                    pass
        return output_path

    def images_to_video(self, image_paths, output_path, voiceover_scripts=None,
                        voiceover_path=None,
                        bgm_path=None, duration_per_image=4.0,
                        transition_duration=0.5, resolution=(1920, 1080),
                        fps=30, tts_voice="zh-CN-XiaoxiaoNeural"):
        """图片 → 生成配音 → 合成 → 加BGM → 出MP4 一条龙"""
        _check_available()
        output_path = _normalize_path(output_path)
        print("=" * 50)
        print("  🎬 MoviePy 一条龙出片")
        print("=" * 50)

        temp_dir = os.path.join(os.path.dirname(output_path) or ".", "_temp")
        os.makedirs(temp_dir, exist_ok=True)

        cleanup_files = []
        try:
            local_voiceover = voiceover_path  # 外部配音路径
            if voiceover_path:
                # 外部配音，直接用
                print(f"\n[🎤] 使用外部配音: {voiceover_path}")
            elif voiceover_scripts:
                print("\n[🎤] 生成配音...")
                local_voiceover = os.path.join(temp_dir, "voiceover.mp3")

                async def gen_tts():
                    import edge_tts
                    full_text = "。".join(voiceover_scripts)
                    await edge_tts.Communicate(full_text, tts_voice).save(local_voiceover)

                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 已有事件循环运行（如Jupyter/异步环境），用新线程
                        import threading
                        def _run():
                            asyncio.run(gen_tts())
                        t = threading.Thread(target=_run, daemon=True)
                        t.start()
                        t.join()
                    else:
                        loop.run_until_complete(gen_tts())
                except RuntimeError:
                    asyncio.run(gen_tts())
                if os.path.isfile(local_voiceover):
                    print(f"  ✅ 配音: {os.path.getsize(local_voiceover) // 1024}KB")
                    cleanup_files.append(local_voiceover)
                else:
                    print("  [⚠️] 配音生成失败")
                    local_voiceover = None

            print("\n[🖼️] 生成幻灯片视频...")
            video_temp = os.path.join(temp_dir, "slideshow.mp4")
            cleanup_files.append(video_temp)
            self.make_slideshow(image_paths, video_temp,
                                duration_per_image=duration_per_image,
                                transition_duration=transition_duration,
                                resolution=resolution, fps=fps)

            print("\n[🎵] 合成音频...")
            result = self.add_audio(video_temp, voiceover_path=local_voiceover,
                                    bgm_path=bgm_path, output_path=output_path)

            print(f"\n✅ 成品: {output_path}")
            return result
        finally:
            # 清理临时文件，失败仅打印警告
            for f in cleanup_files:
                if f and os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception as e:
                        print(f"  [⚠️] 清理临时文件失败: {f} — {e}")
            if os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except Exception:
                    pass
