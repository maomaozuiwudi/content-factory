"""
素材分析模块
分析用户给的素材（图片/视频），提取特征：
- 图片：尺寸、颜色主色调、是否有文字、文件大小、类型
- 视频：时长、分辨率、帧率、文件大小

输出结构化的素材描述，供文案引擎和剪辑引擎使用
"""

import os
import logging
from pathlib import Path
from PIL import Image

from utils.config_loader import resolve_path

logger = logging.getLogger(__name__)


# ---------- 支持的格式 ----------

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
SUPPORTED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


# ---------- 图片分析 ----------

def analyze_image(image_path):
    """
    分析单张图片

    Returns:
        dict: {
            "path": str,
            "filename": str,
            "type": "image",
            "format": str,
            "width": int,
            "height": int,
            "ratio": float,
            "file_size_kb": float,
            "dominant_color": str,     # 主色调 hex
            "has_text": bool,          # 粗略判断是否有文字（通过对比度）
            "orientation": str,        # portrait | landscape | square
        }
    """
    if not os.path.isfile(image_path):
        return {"error": f"文件不存在或不是普通文件: {image_path}"}

    try:
        with Image.open(image_path) as img:
            w, h = img.size
            ratio = round(w / h, 4)

            # 文件大小
            file_size_kb = round(os.path.getsize(image_path) / 1024, 2)

            # 主色调（缩略图采样）
            dominant_color = _get_dominant_color(img)

            # 方向
            if w > h * 1.1:
                orientation = "landscape"
            elif h > w * 1.1:
                orientation = "portrait"
            else:
                orientation = "square"

            # 是否有文字（启发式：高对比度区域比例）
            has_text = _detect_text_region(img)

            return {
                "path": os.path.abspath(image_path),
                "filename": os.path.basename(image_path),
                "type": "image",
                "format": img.format or "unknown",
                "width": w,
                "height": h,
                "ratio": ratio,
                "file_size_kb": file_size_kb,
                "dominant_color": dominant_color,
                "has_text": has_text,
                "orientation": orientation,
            }
    except Exception as e:
        logger.warning(f"分析图片失败 {image_path}: {e}")
        return {"error": str(e), "path": image_path}


def _get_dominant_color(img, sample_size=50):
    """获取图片主色调（缩略图采样取平均值）"""
    try:
        # 先将图片统一转为 RGB 模式（处理 P 模式/调色板模式）
        if img.mode == "P":
            rgb_img = img.convert("RGB")
        else:
            rgb_img = img
        small = rgb_img.copy()
        small.thumbnail((sample_size, sample_size))
        pixels = list(small.getdata())

        if not pixels:
            return "#808080"

        # 如果是RGBA，转RGB
        if len(pixels[0]) >= 4:
            pixels = [(p[0], p[1], p[2]) for p in pixels]

        # 计算平均色
        r_total = sum(p[0] for p in pixels)
        g_total = sum(p[1] for p in pixels)
        b_total = sum(p[2] for p in pixels)
        n = len(pixels)

        return f"#{r_total // n:02x}{g_total // n:02x}{b_total // n:02x}"
    except Exception as e:
        logger.warning(f"_get_dominant_color 异常: {e}")
        return "#808080"


def _detect_text_region(img, threshold=50):
    """
    粗略判断图片中是否有文字区域
    通过检测局部对比度变化来估算
    """
    try:
        gray = img.convert("L")
        w, h = gray.size
        # 取中间区域采样
        sample = gray.crop((w // 4, h // 4, w * 3 // 4, h * 3 // 4))
        pixels = list(sample.getdata())
        if not pixels:
            return False

        # 灰度图下每个像素是int，无需检查长度
        # 计算像素值方差，方差大说明对比度高，可能存在文字
        mean = sum(pixels) / len(pixels)
        variance = sum((p - mean) ** 2 for p in pixels) / len(pixels)

        return variance > threshold
    except Exception as e:
        logger.warning(f"_detect_text_region 异常: {e}")
        return False


# ---------- 视频分析 ----------

def analyze_video(video_path):
    """
    分析视频文件（仅文件元数据，不调用ffmpeg）

    Returns:
        dict: {
            "path": str,
            "filename": str,
            "type": "video",
            "format": str,
            "file_size_mb": float,
            "info": str,    # 额外信息
        }
    """
    if not os.path.isfile(video_path):
        return {"error": f"文件不存在或不是普通文件: {video_path}"}

    try:
        ext = os.path.splitext(video_path)[1].lower()
        file_size_mb = round(os.path.getsize(video_path) / (1024 * 1024), 2)

        return {
            "path": os.path.abspath(video_path),
            "filename": os.path.basename(video_path),
            "type": "video",
            "format": ext,
            "file_size_mb": file_size_mb,
            "info": f"视频文件，大小 {file_size_mb}MB",
        }
    except Exception as e:
        return {"error": str(e), "path": video_path}


# ---------- 批量分析 ----------

def analyze_materials(paths):
    """
    分析多个素材（图片/视频混合）

    Args:
        paths: 文件路径列表，或目录路径

    Returns:
        dict: {
            "images": [分析结果...],
            "videos": [分析结果...],
            "summary": str,
        }
    """
    # 校验 paths 参数类型
    if isinstance(paths, str):
        if os.path.isdir(paths):
            all_files = []
            for root, _, files in os.walk(paths):
                for f in files:
                    all_files.append(os.path.join(root, f))
            paths = all_files
        else:
            paths = [paths]
    elif not hasattr(paths, '__iter__'):
        raise TypeError(f"paths 参数应为字符串或可迭代路径集合，得到 {type(paths).__name__}")

    images = []
    videos = []
    unknown = []

    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext in SUPPORTED_IMAGE_EXTS:
            result = analyze_image(p)
            if "error" not in result:
                images.append(result)
            else:
                unknown.append(result)
        elif ext in SUPPORTED_VIDEO_EXTS:
            result = analyze_video(p)
            if "error" not in result:
                videos.append(result)
            else:
                unknown.append(result)
        else:
            unknown.append({"path": p, "type": "unknown", "info": f"不支持的格式: {ext}"})

    # 生成摘要
    summary_parts = []
    if images:
        orientations = [i["orientation"] for i in images]
        portrait = orientations.count("portrait")
        landscape = orientations.count("landscape")
        summary_parts.append(f"图片 {len(images)} 张（竖图{portrait} 横图{landscape} 方图{len([o for o in orientations if o=='square'])}）")
    if videos:
        summary_parts.append(f"视频 {len(videos)} 个")

    if not summary_parts:
        summary_parts.append("无有效素材")

    return {
        "images": images,
        "videos": videos,
        "unknown": unknown,
        "summary": " | ".join(summary_parts),
        "total": len(images) + len(videos),
    }


def format_analysis_for_prompt(analysis_result):
    """将分析结果格式化为LLM可读的文本"""
    parts = [f"素材分析报告: {analysis_result['summary']}"]

    if analysis_result["images"]:
        parts.append("\n图片列表:")
        for img in analysis_result["images"][:10]:
            parts.append(
                f"  - {img['filename']}: {img['width']}x{img['height']} "
                f"{img['orientation']} 主色{img['dominant_color']} "
                f"{'带文字' if img['has_text'] else '无文字'}"
            )

    if analysis_result["videos"]:
        parts.append("\n视频列表:")
        for vid in analysis_result["videos"]:
            parts.append(f"  - {vid['filename']}: {vid['file_size_mb']}MB")

    return "\n".join(parts)


# 测试
if __name__ == "__main__":
    print("=== 素材分析测试 ===\n")

    # 创建测试图片
    test_dir = resolve_path("output/test_materials/")
    os.makedirs(test_dir, exist_ok=True)

    from PIL import Image, ImageDraw

    # 竖图带文字
    img1 = Image.new("RGB", (1080, 1440), (30, 30, 60))
    draw = ImageDraw.Draw(img1)
    draw.text((100, 200), "测试文字区域", fill=(255, 255, 255))
    img1.save(os.path.join(test_dir, "portrait_text.png"))

    # 横图
    img2 = Image.new("RGB", (1920, 1080), (200, 100, 50))
    img2.save(os.path.join(test_dir, "landscape.png"))

    # 方图纯色
    img3 = Image.new("RGB", (800, 800), (100, 180, 100))
    img3.save(os.path.join(test_dir, "square_plain.png"))

    # 分析单个图片
    print("--- 单张图片分析 ---")
    result = analyze_image(os.path.join(test_dir, "portrait_text.png"))
    for k, v in result.items():
        print(f"  {k}: {v}")

    # 批量分析目录
    print("\n--- 批量分析 ---")
    batch = analyze_materials(test_dir)
    print(f"集合: {batch['summary']}")
    print(f"格式化为Prompt:")
    print(format_analysis_for_prompt(batch))

    print("\nOK")
