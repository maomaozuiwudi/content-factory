"""
FFmpeg 视频合成 Provider — 占位文件
"""


class FFmpegVideo:
    """FFmpeg 驱动的视频合成器（待实现）"""

    def compose(self, image_paths, text="", output_path="output.mp4",
                duration_per_image=4.0, resolution=(1920, 1080)):
        raise NotImplementedError("FFmpegVideo 待实现")
