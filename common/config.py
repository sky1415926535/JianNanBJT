"""
配置管理模块
- 默认配置定义
- config.json 读写
"""
import json
import logging

from .paths import CONFIG_FILE

log = logging.getLogger("Common.Config")


# ============================================================
# 默认配置（与 main.py v3.2 一致）
# ============================================================
DEFAULT_CONFIG = {
    "adb": {
        "device": "emulator-5554",
        "path": "",
    },
    "screen": {
        "width": 1920,
        "height": 1080,
    },
    "disc": {
        "center_x": 1535,
        "center_y": 505,
        "outer_radius": 170,
        "bead_radius": 135,
    },
    "zones": {
        "blue_start": 0,
        "blue_end": 300,
        "yellow_start": 300,
        "yellow_end": 360,
    },
    "buttons": {
        "reel_x": 1540,
        "reel_y": 825,
        "claim_x": 960,
        "claim_y": 750,
        "retry_x": 960,
        "retry_y": 850,
    },
    "detection": {
        "bead_brightness_min": 180,
        "bead_min_area": 15,
        "bead_max_area": 300,
        "match_threshold": 0.80,
        "disc_lost_timeout": 4.0,
        "bead_miss_threshold": 8,
        "result_wait": 2.0,
        "restart_wait": 2.5,
    },
    "timing": {
        "screenshot_cooldown": 0.06,
        "min_click_interval": 0.20,
        "animation_wait": 0.3,
        "popup_wait": 0.8,
        "idle_timeout": 15.0,
        "activity_timeout": 60.0,
    },
    "fishing": {
        "max_rounds": 999,
        "prefer_yellow": True,
        "click_blue_probability": 1.0,
    },
    "retry": {
        "retry_on_failure": True,
        "max_retries": 0,
        "retry_delay": 2.0,
    },
    # ============================================================
    # 大地图州府切换配置（v4.0 新增）
    # ============================================================
    "prefecture": {
        "target": "白雪镇",
        "swipe_count": 3,
        "swipe_distance": 300,
        "swipe_duration": 500,
    },
    # ============================================================
    # 行囊城镇切换配置（v4.0 新增）
    # ============================================================
    "travel_bag": {
        "target": "白雪镇",
        "scroll_distance": 200,
        "scroll_duration": 300,
        "max_scrolls": 10,
    },
}


# ============================================================
# 配置读写函数
# ============================================================
def load_config():
    """读取 config.json 配置文件，不存在则返回默认配置副本"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    """将配置字典写入 config.json"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    log.info(f"配置已保存: {CONFIG_FILE}")
