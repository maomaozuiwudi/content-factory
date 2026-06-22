"""
Pillow 生图 Provider

从 modules/local_image.py 迁移而来，保持原有行为不变。
"""

import os

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils.config_loader import get, resolve_path


class PillowImage:
    """纯 Pillow 驱动的本地生图器"""

    # ---------- 字体 ----------

    def _get_font(self, size=36, bold=False):
        """获取字体，默认字体不支持中文时回退"""
        font_path = get("image_defaults.font_path", "")
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)

        candidates = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/msyhbd.ttc",
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/STSONG.TTF",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        ]
        if bold:
            candidates.insert(0, "C:/Windows/Fonts/msyhbd.ttc")

        for cf in candidates:
            if os.path.exists(cf):
                try:
                    return ImageFont.truetype(cf, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    # ---------- 即梦背景（可选） ----------

    def _try_jimeng_background(self, prompt, size=(1080, 1440)):
        """尝试用即梦生成封面背景图，失败静默回退"""
        try:
            from modules.jimeng_client import JimengClient
            client = JimengClient.from_config()
            if not client.ready:
                return None
            result = client.generate_image(prompt, size=size)
            if "urls" in result and result["urls"]:
                import requests
                from io import BytesIO
                url = result["urls"][0]
                resp = requests.get(url, timeout=30)
                img = Image.open(BytesIO(resp.content))
                img = img.resize(size, Image.LANCZOS)
                print(f"[🎨 即梦] 封面背景图生成成功")
                return img
            return None
        except Exception as e:
            print(f"[⚠️ 即梦] 背景图失败，回退本地: {e}")
            return None

    # ---------- 颜色工具 ----------

    def _hex_to_rgb(self, hex_color):
        """#RRGGBB 或 #RRGGBBAA 转 (R,G,B)"""
        try:
            hex_color = hex_color.lstrip("#")
            if len(hex_color) >= 6:
                return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass
        return (255, 255, 255)

    def _get_image_defaults(self):
        """获取默认生图参数"""
        return {
            "width": get("image_defaults.width", 1080),
            "height": get("image_defaults.height", 1440),
            "bg_color": get("image_defaults.bg_color", "#1A1A2E"),
            "text_color": get("image_defaults.text_color", "#FFFFFF"),
            "accent_color": get("image_defaults.accent_color", "#E94560"),
            "font_size_title": get("image_defaults.font_size_title", 64),
            "font_size_subtitle": get("image_defaults.font_size_subtitle", 36),
        }

    def _auto_break_text(self, text, max_chars_per_line=10):
        """自动换行（中文字符计数）"""
        lines = []
        current = ""
        for char in text:
            current += char
            if len(current) >= max_chars_per_line:
                lines.append(current)
                current = ""
        if current:
            lines.append(current)
        return lines

    # ---------- 核心功能 ----------

    def generate_card(self, title, subtitle="", bg_color=None, text_color=None, accent_color=None,
                      width=None, height=None, output_path=None):
        """生成文字卡片图

        Args:
            title: 标题文字（会自动换行）
            subtitle: 副标题
            bg_color: 背景色 #RRGGBB
            text_color: 文字颜色
            accent_color: 强调色
            width, height: 图片尺寸
            output_path: 输出路径，None则自动生成

        Returns:
            str: 图片输出路径
        """
        params = self._get_image_defaults()
        bg_color = bg_color or params["bg_color"]
        text_color = text_color or params["text_color"]
        accent_color = accent_color or params["accent_color"]
        width = width or params["width"]
        height = height or params["height"]

        img = Image.new("RGB", (width, height), self._hex_to_rgb(bg_color))
        draw = ImageDraw.Draw(img)

        bar_height = 8
        draw.rectangle([0, 0, width, bar_height], fill=self._hex_to_rgb(accent_color))
        draw.rectangle([0, height - bar_height, width, height], fill=self._hex_to_rgb(accent_color))

        font_title = self._get_font(params["font_size_title"], bold=True)
        title_lines = self._auto_break_text(title, max_chars_per_line=8)
        line_height = params["font_size_title"] + 12
        start_y = (height - len(title_lines) * line_height) // 2 - 40

        for i, line in enumerate(title_lines):
            bbox = draw.textbbox((0, 0), line, font=font_title)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            y = start_y + i * line_height
            draw.text((x, y), line, fill=self._hex_to_rgb(text_color), font=font_title)

        if subtitle:
            font_sub = self._get_font(params["font_size_subtitle"])
            sub_lines = self._auto_break_text(subtitle, max_chars_per_line=14)
            sub_y = start_y + len(title_lines) * line_height + 40
            for line in sub_lines:
                bbox = draw.textbbox((0, 0), line, font=font_sub)
                tw = bbox[2] - bbox[0]
                x = (width - tw) // 2
                draw.text((x, sub_y), line, fill=self._hex_to_rgb(accent_color), font=font_sub)
                sub_y += params["font_size_subtitle"] + 8

        output_dir = resolve_path(get("output.image_dir", "output/images/"))
        os.makedirs(output_dir, exist_ok=True)

        if output_path is None:
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:20]
            output_path = os.path.join(output_dir, f"card_{safe_title}.png")
        else:
            output_path = os.path.normpath(output_path)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"[🖼️ 生图] 卡片已保存: {output_path}")
        return output_path

    def generate_cover(self, title, subtitle="", tags=None, output_path=None):
        """生成小红书封面图

        Args:
            title: 封面标题
            subtitle: 副标题（可选）
            tags: 标签列表（可选）
            output_path: 输出路径

        Returns:
            str: 输出路径
        """
        params = self._get_image_defaults()
        width, height = params["width"], params["height"]
        bg_color = self._hex_to_rgb(params["bg_color"])
        text_color = params["text_color"]
        accent_color = params["accent_color"]

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        jimeng_img = self._try_jimeng_background(title, size=(width, height))
        if jimeng_img:
            img = jimeng_img
            draw = ImageDraw.Draw(img)
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 80))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
            draw = ImageDraw.Draw(img)

        border_w = 20
        draw.rectangle([border_w, border_w, width - border_w, height - border_w],
                       outline=self._hex_to_rgb(accent_color), width=4)

        if tags:
            font_tag = self._get_font(28)
            tag_text = "  ".join(f"#{t}" for t in tags[:4])
            bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, 120), tag_text, fill=self._hex_to_rgb(accent_color), font=font_tag)

        font_title = self._get_font(72, bold=True)
        title_lines = self._auto_break_text(title, max_chars_per_line=7)
        line_h = 80
        total_h = len(title_lines) * line_h
        start_y = (height - total_h) // 2 - 40

        for i, line in enumerate(title_lines):
            bbox = draw.textbbox((0, 0), line, font=font_title)
            tw = bbox[2] - bbox[0]
            x = (width - tw) // 2
            draw.text((x, start_y + i * line_h), line, fill=self._hex_to_rgb(text_color), font=font_title)

        if subtitle:
            font_sub = self._get_font(32)
            sub_y = start_y + len(title_lines) * line_h + 40
            sub_lines = self._auto_break_text(subtitle, max_chars_per_line=16)
            for line in sub_lines:
                bbox = draw.textbbox((0, 0), line, font=font_sub)
                tw = bbox[2] - bbox[0]
                draw.text(((width - tw) // 2, sub_y), line, fill=self._hex_to_rgb(accent_color), font=font_sub)
                sub_y += 40

        font_water = self._get_font(24)
        watermark = "工具猫 · 小红书内容工坊"
        bbox = draw.textbbox((0, 0), watermark, font=font_water)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, height - 80), watermark,
                  fill=(150, 150, 150), font=font_water)

        output_dir = resolve_path(get("output.image_dir", "output/images/"))
        os.makedirs(output_dir, exist_ok=True)

        if output_path is None:
            safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:20]
            output_path = os.path.join(output_dir, f"cover_{safe_title}.png")
        else:
            output_path = os.path.normpath(output_path)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        img.save(output_path, "PNG")
        print(f"[🖼️ 生图] 封面已保存: {output_path}")
        return output_path

    def stitch_images(self, image_paths, layout="grid", output_path=None):
        """多图拼接 — 将多张图片合成一张

        Args:
            image_paths: 图片路径列表
            layout: 'grid' | 'vertical' | 'horizontal'
            output_path: 输出路径

        Returns:
            str: 输出路径
        """
        if not image_paths:
            raise ValueError("没有图片可拼接")

        images = []
        for p in image_paths:
            try:
                img = Image.open(p).convert("RGB")
                images.append(img)
            except Exception as e:
                print(f"[⚠️ 生图] 加载图片失败: {p} — {e}")

        if not images:
            raise ValueError("没有有效的图片")

        if layout == "grid":
            n = len(images)
            cols = 2 if n >= 4 else (n if n <= 2 else 2)
            rows = (n + cols - 1) // cols
            target_w = 1080 // cols
            target_h = 1440 // rows
            resized = [img.resize((target_w, target_h), Image.LANCZOS) for img in images]
            canvas = Image.new("RGB", (target_w * cols, target_h * rows), (255, 255, 255))
            for i, img in enumerate(resized):
                x = (i % cols) * target_w
                y = (i // cols) * target_h
                canvas.paste(img, (x, y))

        elif layout == "vertical":
            target_w = 1080
            total_h = sum(int(img.height * target_w / img.width) for img in images)
            canvas = Image.new("RGB", (target_w, total_h), (255, 255, 255))
            y = 0
            for img in images:
                ratio = target_w / img.width
                h = int(img.height * ratio)
                resized = img.resize((target_w, h), Image.LANCZOS)
                canvas.paste(resized, (0, y))
                y += h

        elif layout == "horizontal":
            target_h = 1440
            total_w = sum(int(img.width * target_h / img.height) for img in images)
            canvas = Image.new("RGB", (total_w, target_h), (255, 255, 255))
            x = 0
            for img in images:
                ratio = target_h / img.height
                w = int(img.width * ratio)
                resized = img.resize((w, target_h), Image.LANCZOS)
                canvas.paste(resized, (x, 0))
                x += w
        else:
            raise ValueError(f"不支持的布局: {layout}")

        output_dir = resolve_path(get("output.image_dir", "output/images/"))
        os.makedirs(output_dir, exist_ok=True)

        if output_path is None:
            output_path = os.path.join(output_dir, f"stitch_{layout}_{len(images)}pics.png")
        else:
            output_path = os.path.normpath(output_path)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        canvas.save(output_path, "PNG")
        print(f"[🖼️ 生图] 拼接图已保存: {output_path}")
        return output_path
