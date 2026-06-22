"""
视觉分析模块 — Kimi K2.5 驱动
分析图片/视频内容，生成画面描述，
让文案和配音精准对应素材画面内容。
"""

import os
import cv2
import base64
import requests
from pathlib import Path

# ---------- Kimi K2.5 配置 ----------

KIMI_BASE_URL = "https://api.moonshot.cn/v1"
KIMI_MODEL = "kimi-k2.5"

# 从 Hermes 配置文件读取 API Key
_HERMES_CONFIG_PATH = Path(
    os.environ.get("HERMES_CONFIG_PATH",
                   str(Path.home() / "AppData/Local/hermes/config.yaml"))
)


def _get_kimi_api_key():
    """从 Hermes config.yaml 读取 auxiliary.vision.api_key"""
    try:
        import yaml
        with open(_HERMES_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        key = cfg.get("auxiliary", {}).get("vision", {}).get("api_key", "")
        return key or os.environ.get("KIMI_API_KEY", "")
    except Exception:
        return os.environ.get("KIMI_API_KEY", "")


KIMI_API_KEY = _get_kimi_api_key()


# ---------- 工具函数 ----------

def encode_image(image_path):
    """图片转 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_image_data_url(image_path):
    """构建 data:image/xxx;base64,xxxx 格式的 URL"""
    b64 = encode_image(image_path)
    ext = Path(image_path).suffix[1:] or "png"
    if ext.lower() == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b64}"


def _safe_get_response_content(resp):
    """安全地从API响应中提取 content 字段"""
    try:
        data = resp.json()
        choices = data.get("choices", [])
        if choices and len(choices) > 0:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            return content
    except (ValueError, KeyError, IndexError, AttributeError):
        pass
    return None


def _retry_vision_with_short_prompt(content_items, max_tokens=200):
    """Kimi返回空时用短prompt重试一次"""
    try:
        resp = requests.post(
            f"{KIMI_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {KIMI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": KIMI_MODEL,
                "messages": [{"role": "user", "content": content_items}],
                "max_tokens": max_tokens,
            },
            timeout=30,
        )
        if resp.status_code == 200:
            c = _safe_get_response_content(resp)
            if c and c.strip():
                return c.strip()
    except Exception:
        pass
    return None


# ---------- 图片分析 ----------

def analyze_image(image_path):
    """
    用 Kimi K2.5 分析单张图片内容

    Args:
        image_path: 图片文件路径

    Returns:
        str: 画面描述（如 "一张 VS Code 截图，展示 Python 代码，窗口标题是 'test.py'"）
             如果 API 不可用，返回降级文本。
    """
    if not KIMI_API_KEY:
        return "[视觉分析未配置: 缺少 Kimi API Key]"

    if not os.path.isfile(image_path):
        return f"[视觉分析: 文件不存在 {image_path}]"

    data_url = _build_image_data_url(image_path)

    try:
        resp = requests.post(
            f"{KIMI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {KIMI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": KIMI_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "请用一句话准确描述这张图片/截图的内容，"
                                    "说清楚画面上有什么、是什么场景。"
                                    "不要评价好坏，只描述客观内容。"
                                ),
                            },
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
                "max_tokens": 200,
            },
            timeout=30,
        )

        if resp.status_code == 200:
            content = _safe_get_response_content(resp)
            if content and content.strip():
                return content.strip()
            # 内容为空时重试一次（Kimi 间歇性空返回）
            c2 = _retry_vision_with_short_prompt([
                {"type": "text", "text": "用一句话描述这张图片的内容"},
                {"type": "image_url", "image_url": {"url": data_url}}
            ], max_tokens=200)
            if c2:
                return c2
            return f"[素材图片: {os.path.basename(image_path)}]"
        else:
            return f"[视觉分析失败: HTTP {resp.status_code}]"
    except Exception as e:
        return f"[视觉分析异常: {e}]"


# ---------- 视频分析 ----------

def analyze_video(video_path, max_frames=3):
    """
    用 Kimi K2.5 分析视频关键帧

    提取视频中的几个关键帧（均匀采样），描述画面内容

    Args:
        video_path: 视频文件路径
        max_frames: 提取的关键帧数量（默认 3）

    Returns:
        str: 视频内容描述
    """
    if not KIMI_API_KEY:
        return "[视觉分析未配置: 缺少 Kimi API Key]"

    if not os.path.isfile(video_path):
        return f"[视觉分析: 文件不存在 {video_path}]"

    # 确保 max_frames 至少为 1
    max_frames = max(1, max_frames)

    cap = cv2.VideoCapture(video_path)
    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        duration = total_frames / fps if fps > 0 else 0

        if total_frames <= 0:
            return f"[视频: {os.path.basename(video_path)}, {duration:.1f}s，无法提取帧]"

        # 均匀采样 max_frames 个关键帧
        frames = []
        for i in range(max_frames):
            target_frame = int(total_frames * i / max_frames)
            # 避免最后一帧超出范围
            target_frame = min(target_frame, total_frames - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = cap.read()
            if ret:
                # 压缩到 max 800px 宽，减少 token 消耗
                h, w = frame.shape[:2]
                if w > 800:
                    scale = 800 / w
                    new_w, new_h = int(w * scale), int(h * scale)
                    frame = cv2.resize(frame, (new_w, new_h))
                _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                frames.append(base64.b64encode(buf).decode("utf-8"))
    finally:
        cap.release()

    if not frames:
        return f"[视频: {os.path.basename(video_path)}，无法提取帧]"

    # 构建多帧分析请求
    content = [
        {
            "type": "text",
            "text": (
                f"这是一个视频（{duration:.1f}秒），"
                f"以下是按时间顺序抽取的 {len(frames)} 个画面关键帧。"
                f"请描述这个视频的内容和场景变化："
            ),
        }
    ]
    for i, b64 in enumerate(frames):
        time_pos = i * duration / max_frames
        content.append({"type": "text", "text": f"[{time_pos:.1f}秒处]"})
        content.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
        )

    content.append(
        {
            "type": "text",
            "text": "请用一两句话概括这个视频的内容，包括画面里有什么、在做什么。",
        }
    )

    try:
        resp = requests.post(
            f"{KIMI_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {KIMI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": KIMI_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 300,
            },
            timeout=60,
        )

        if resp.status_code == 200:
            content_text = _safe_get_response_content(resp)
            if content_text and content_text.strip():
                return content_text.strip()
            # 内容为空时重试一次（Kimi 间歇性空返回）
            retry_content = [
                {"type": "text", "text": "用一句话描述这个视频的内容"},
            ]
            for i, b64 in enumerate(frames):
                time_pos = i * duration / max_frames
                retry_content.append({"type": "text", "text": f"[{time_pos:.1f}秒处]"})
                retry_content.append(
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                )
            c2 = _retry_vision_with_short_prompt(retry_content, max_tokens=300)
            if c2:
                return c2
            return f"[视频素材: {os.path.basename(video_path)}]"
        else:
            return f"[视频分析失败: HTTP {resp.status_code}]"
    except Exception as e:
        return f"[视频分析异常: {e}]"


# ---------- 批量分析 ----------

def analyze_all_materials(paths):
    """
    批量分析所有素材（图片 + 视频）

    Args:
        paths: 素材路径列表

    Returns:
        dict: {material_path: vision_description}
    """
    results = {}
    for p in paths:
        if not os.path.exists(p):
            results[p] = f"[文件不存在: {p}]"
            continue

        ext = os.path.splitext(p)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
            results[p] = analyze_image(p)
        elif ext in (".mp4", ".mov", ".avi", ".mkv", ".webm"):
            results[p] = analyze_video(p)
        else:
            results[p] = f"[不支持的文件类型: {ext}]"

    return results


# ---------- 测试入口 ----------

if __name__ == "__main__":
    print("=== 视觉分析模块测试 ===\n")

    print(f"API Key 状态: {'已配置' if KIMI_API_KEY else '未配置'}")

    # 测试图片分析
    test_dir = Path(__file__).parent.parent / "output/test_materials"
    test_file = test_dir / "test_0.png"
    if test_file.exists():
        print(f"\n--- 分析图片: {test_file} ---")
        desc = analyze_image(str(test_file))
        print(f"  描述: {desc}")
    else:
        print(f"\n[⚠️] 测试图片不存在: {test_file}")

    print("\nOK")
