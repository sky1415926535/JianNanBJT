"""
大地图州府切换模块（v4.0）

功能：在大地图上定位并切换到目标州府
- 打开大地图界面
- 通过滑动和图像匹配定位目标州府
- 点击进入目标州府

当前为骨架代码，具体检测逻辑待截图确认后填充。
"""
import time
import logging

from common import ADB, Vision, load_config

log = logging.getLogger("MapSwitch")


class PrefectureSwitcher:
    """州府切换器"""

    def __init__(self, cfg=None):
        self.cfg = cfg or load_config()
        self.pref_cfg = self.cfg.get("prefecture", {})
        self.target = self.pref_cfg.get("target", "白雪镇")
        self.vision = Vision(self.cfg)

    def switch_to(self, target=None):
        """
        切换到目标州府
        target: 州府名称，默认使用配置文件中的 target
        返回: bool
        """
        target = target or self.target
        log.info(f"[州府切换] 目标: {target}")

        # TODO: 等待截图确认大地图UI后实现
        # 预计流程:
        # 1. 确认当前在大地图界面
        # 2. 截图识别当前可见的州府标记
        # 3. 若目标不可见，滑动地图
        # 4. 定位目标州府图标/文字
        # 5. 点击进入

        log.warning("  [WIP] 州府切换模块为骨架代码，待截图确认后实现")
        return False

    def is_on_big_map(self, img):
        """检测当前是否在大地图界面（骨架）"""
        # TODO: 通过特征检测确认当前界面
        # 如检测底部"行囊"/"州府"等UI元素
        return False

    def find_prefecture_marker(self, img, name):
        """在大地图截图中查找目标州府标记（骨架）"""
        # TODO: 通过颜色、形状或文字匹配定位州府
        return None

    def swipe_map(self, direction="up", distance=300):
        """滑动大地图"""
        w = self.cfg["screen"]["width"]
        h = self.cfg["screen"]["height"]
        if direction == "up":
            ADB.swipe(w // 2, h * 2 // 3, w // 2, h * 2 // 3 - distance)
        elif direction == "down":
            ADB.swipe(w // 2, h // 3, w // 2, h // 3 + distance)
        elif direction == "left":
            ADB.swipe(w * 2 // 3, h // 2, w * 2 // 3 - distance, h // 2)
        elif direction == "right":
            ADB.swipe(w // 3, h // 2, w // 3 + distance, h // 2)
        time.sleep(0.5)
