"""全自动量产 — 调用 main.py 的模式三"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.config_loader import load_config
load_config()
from main import XHSWorkshop
ws = XHSWorkshop()
ws.mode_auto_full()
