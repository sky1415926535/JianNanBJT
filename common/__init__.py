# ============================================================
# common — 江南百景图自动化脚本公共模块
# ============================================================

from .paths import SCRIPT_DIR, TEMPLATE_DIR, SCREENSHOT_DIR, CONFIG_FILE, LOG_FILE
from .adb import ADB, find_adb, detect_device
from .vision import Vision
from .config import load_config, save_config, DEFAULT_CONFIG

__all__ = [
    "SCRIPT_DIR", "TEMPLATE_DIR", "SCREENSHOT_DIR", "CONFIG_FILE", "LOG_FILE",
    "ADB", "find_adb", "detect_device",
    "Vision",
    "load_config", "save_config", "DEFAULT_CONFIG",
]
