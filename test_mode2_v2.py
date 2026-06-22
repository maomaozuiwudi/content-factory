"""测试模式二新流程 — 模拟用户输入"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from utils.config_loader import load_config
load_config()
from main import XHSWorkshop

# 模拟用户输入流
test_inputs = [
    "y\n",       # 步骤3：文案满意？→ y
    "n\n",       # 步骤5：有素材吗？→ n
    "1\n",       # 图还是视频？→ 1（图片）
    "1\n",       # 引擎选择→ 1（脚本）
]
# 自动用第一个，后面的用 input() 让用户手动输入
import builtins
_input = builtins.input
input_counter = [0]
def mock_input(prompt=""):
    i = input_counter[0]
    if i < len(test_inputs):
        input_counter[0] += 1
        val = test_inputs[i].strip()
        print(f"{prompt}{val}")  # 显示模拟输入
        return val
    return _input(prompt)

builtins.input = mock_input

ws = XHSWorkshop()
ws.mode_topic_driven(topic='穿搭')
