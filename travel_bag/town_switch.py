"""
行囊城镇切换模块（v4.0）

功能：在行囊界面中切换目标城镇
- 打开行囊界面
- 上下滚动城镇列表
- 匹配目标城镇名称
- 点击进入目标城镇

当前为骨架代码，具体检测逻辑待截图确认后填充。
"""
import time
import logging

from common import ADB, Vision, load_config

log = logging.getLogger("TravelBag")


class TownSwitcher:
    """行囊城镇切换器"""

    def __init__(self, cfg=None):
        self.cfg = cfg or load_config()
        self.bag_cfg = self.cfg.get("travel_bag", {})
        self.target = self.bag_cfg.get("target", "白雪镇")
        self.vision = Vision(self.cfg)

    def switch_to(self, target=None):
        """
        在行囊中切换到目标城镇
        target: 城镇名称，默认使用配置文件中的 target
        返回: bool
        """
        target = target or self.target
        log.info(f"[行囊切换] 目标: {target}")

        # TODO: 等待截图确认行囊UI后实现
        # 预计流程:
        # 1. 确认当前在行囊界面
        # 2. 截图识别列表中的城镇项
        # 3. 若目标不在可视区域，上下滚动
        # 4. 匹配目标城镇名称/图标
        # 5. 点击进入

        log.warning("  [WIP] 行囊城镇切换模块为骨架代码，待截图确认后实现")
        return False

    def is_in_travel_bag(self, img):
        """检测当前是否在行囊界面（骨架）"""
        # TODO: 通过特征检测确认当前界面
        # 如检测行囊特有的UI布局元素
        return False

    def scroll_list(self, direction="up", distance=None):
        """
        滚动城镇列表
        direction: "up"(向下滚动查看下面) | "down"(向上滚动查看上面)
        """
        distance = distance or self.bag_cfg.get("scroll_distance", 200)
        duration = self.bag_cfg.get("scroll_duration", 300)
        w = self.cfg["screen"]["width"]
        h = self.cfg["screen"]["height"]

        # 列表区域通常在屏幕中部
        list_x = w // 2
        list_y_top = h // 3
        list_y_bottom = h * 2 // 3

        if direction == "up":
            ADB.swipe(list_x, list_y_bottom, list_x, list_y_bottom - distance, duration)
        else:
            ADB.swipe(list_x, list_y_top, list_x, list_y_top + distance, duration)
        time.sleep(0.3)

    def find_town(self, img, name):
        """在行囊列表截图中查找目标城镇（骨架）"""
        # TODO: 通过颜色、形状或文字匹配定位城镇项
        # 可能的方式:
        #   - 模板匹配（需要城镇图标模板）
        #   - OCR 文字识别
        #   - 颜色特征匹配
        return None

    def tap_town(self, x, y):
        """点击目标城镇进入"""
        ADB.tap(x, y)
        time.sleep(1.0)
