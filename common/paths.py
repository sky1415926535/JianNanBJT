"""
路径常量定义
所有模块共享的文件系统路径
"""
from pathlib import Path

# 项目根目录（JianNanBJT/）
SCRIPT_DIR = Path(__file__).parent.parent.absolute()
TEMPLATE_DIR = SCRIPT_DIR / "templates"
SCREENSHOT_DIR = SCRIPT_DIR / "screenshots"
CONFIG_FILE = SCRIPT_DIR / "config.json"
LOG_FILE = SCRIPT_DIR / "fishing_log.txt"

# 确保必要目录存在
TEMPLATE_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)
