"""
配置文件加载器
从 config.yaml 读取所有配置，提供统一访问接口
"""

import os
import yaml
from pathlib import Path


# 默认配置路径（相对于项目根目录）
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

# 全局单例
_config_cache = None


def load_config(config_path=None):
    """加载配置文件，返回字典"""
    global _config_cache

    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    # 如果路径是相对路径，转为绝对
    config_path = Path(config_path)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        cfg = {}
        print(f"[⚠️] 配置为空: {config_path}")
    elif not isinstance(cfg, dict):
        raise ValueError(f"配置文件格式错误，期望 dict，得到 {type(cfg).__name__}")

    _config_cache = cfg
    return cfg


def get_config():
    """获取缓存的配置，未加载则自动加载默认路径"""
    global _config_cache
    if _config_cache is None:
        load_config()
    return _config_cache


def get(key_path, default=None):
    """
    按点分路径读取配置值
    如：get("api_keys.deepseek.api_key") -> "sk-xxx"
    """
    cfg = get_config()
    parts = key_path.split(".")
    val = cfg
    for part in parts:
        if isinstance(val, dict):
            val = val.get(part)
            if val is None:
                return default
        else:
            return default
    return val if val is not None else default


def resolve_path(relative_path):
    """
    将相对于项目根目录的路径解析为绝对路径
    如果已经是绝对路径则直接返回
    """
    cfg = get_config()
    if cfg is None:
        raise ValueError("配置为空，请检查 config.yaml 文件内容")
    work_dir = cfg.get("project", {}).get("work_dir", "")
    if not work_dir:
        work_dir = str(Path(__file__).parent.parent)

    p = Path(relative_path)
    if p.is_absolute():
        return str(p)
    return str(Path(work_dir) / relative_path)


def ensure_dirs():
    """确保所有输出目录存在"""
    try:
        cfg = get_config()
        dirs = [
            resolve_path(cfg.get("output", {}).get("image_dir", "output/images/")),
            resolve_path(cfg.get("output", {}).get("draft_dir", "output/drafts/")),
            resolve_path(cfg.get("output", {}).get("log_dir", "logs/")),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        return dirs
    except OSError as e:
        print(f"[⚠️] 创建输出目录失败: {e}")
        raise
    except Exception as e:
        print(f"[⚠️] ensure_dirs 异常: {e}")
        raise


# 测试
if __name__ == "__main__":
    cfg = load_config()
    print("=== 配置加载测试 ===")
    work_dir = get('project.work_dir')
    print(f"工作目录: {work_dir if work_dir else '未设置'}")
    api_key = get('api_keys.deepseek.api_key')
    print(f"DeepSeek Key: {api_key[:10] + '...' if api_key else '未设置'}")
    print(f"SearXNG: {get('api_keys.searxng.base_url')}")
    print(f"配图来源: {get('素材来源.配图')}")
    print(f"参考库路径: {get('参考库.path')}")
    print(f"生图宽度: {get('image_defaults.width')}")
    print("OK")
