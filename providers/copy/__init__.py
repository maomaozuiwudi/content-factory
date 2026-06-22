"""文案 Provider 注册表 — 通过 config.yaml 自由切换后端"""

import importlib

from utils.config_loader import get

_REGISTRY = {
    "deepseek": "providers.copy.deepseek.DeepSeekCopy",
    "openai": "providers.copy.openai.OpenAICopy",
}


def get_provider():
    """根据 config.yaml providers.copy 配置返回对应的 provider 实例"""
    name = get("providers.copy", "deepseek")
    if name not in _REGISTRY:
        raise ValueError(f"未知的文案 provider: {name}，可选: {list(_REGISTRY.keys())}")

    mod_path, cls_name = _REGISTRY[name].rsplit(".", 1)
    mod = importlib.import_module(mod_path)
    cls = getattr(mod, cls_name)
    return cls()
