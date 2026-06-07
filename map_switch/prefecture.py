"""
大地图州府切换模块 (v4.0 完整实现)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

功能：在大地图上定位并切换到目标州府。

交互流程（5 步）:
  Step 1 — 进入大地图
           检测当前界面 → 点击大地图按钮 → 等待加载
  Step 2 — 定位州府
           截图 → 三种模式按优先级尝试:
             Mode 1: 坐标直点（最快，需预配置坐标）
             Mode 2: 模板匹配 + 滑动搜索（需模板截图）
             Mode 3: MSER 文字检测（需 OCR，预留）
  Step 3 — 点击州府标记
           执行 ADB.tap(map_coord)
  Step 4 — 确认弹窗
           检测弹出确认对话框 → 点击"确认"按钮
  Step 5 — 等待加载
           等待城镇界面加载完成

配置结构 (config.json → prefecture):
  {
    "target": "白雪镇",                    # 默认目标州府
    "mode": "coordinate",                  # 定位模式: coordinate / template / mser
    "big_map_enter_btn": {"x": N, "y": N}, # 大地图按钮坐标
    "big_map_indicator": {"x": N, "y": N}, # 特征检测点
    "default_confirm_btn": {"x": N, "y": N}, # 通用确认按钮
    "loading_wait": 3.0,                   # 加载等待时间
    "map_search": {                        # 模板匹配搜索参数
      "max_swipes": 8,
      "swipe_distance": 300,
      "swipe_interval": 0.8,
      "directions": ["up", "down", "left", "right"],
      "match_threshold": 0.75
    },
    "prefectures": {                       # 州府列表
      "<name>": {
        "map_coord": {"x": N, "y": N},     # 大地图上的坐标
        "confirm_btn": {"x": N, "y": N},   # 确认按钮(可选, 回退到 default)
        "search_templates": ["xxx.png"]    # 模板匹配用图片
      }
    }
  }

使用方式:
  python launcher.py switch-prefecture --target 白雪镇
  python launcher.py switch-prefecture          # 使用配置中的 target 默认值
  python launcher.py diagnose-map               # 坐标诊断模式(截图+鼠标标记)
"""

import time
import logging
from pathlib import Path

from common import ADB, Vision, load_config, SCREENSHOT_DIR

log = logging.getLogger("MapSwitch")


class PrefectureSwitcher:
    """州府切换器 — 在大地图上定位并切换到目标州府。"""

    # ----------------------------------------------------------------
    # 初始化
    # ----------------------------------------------------------------
    def __init__(self, cfg=None):
        """
        参数:
          cfg: dict | None，配置字典。None 时自动加载 config.json。
        """
        self.cfg = cfg or load_config()
        self.pref_cfg = self.cfg.get("prefecture", {})
        self.target = self.pref_cfg.get("target", "白雪镇")
        self.mode = self.pref_cfg.get("mode", "coordinate")
        self.vision = Vision(self.cfg)
        self._last_swipe_dir_idx = 0  # 滑动方向轮转索引

    # ----------------------------------------------------------------
    # 主入口
    # ----------------------------------------------------------------
    def switch_to(self, target=None):
        """
        切换到目标州府（完整流程入口）。

        执行流程:
          1. _ensure_on_big_map()   → 确保在大地图界面
          2. _navigate_to(target)   → 定位并点击目标州府
          3. _handle_confirm_popup() → 处理确认弹窗
          4. _wait_for_loading()    → 等待城镇加载

        参数:
          target: str | None，州府名称。None 使用配置中的 target 默认值。

        返回:
          bool: 切换成功为 True。
        """
        target = target or self.target
        log.info(f"[州府切换] 目标: {target} (模式: {self.mode})")

        # ---- Step 1: 进入大地图 ----
        if not self._ensure_on_big_map():
            log.error("[州府切换] 无法进入大地图界面")
            return False

        # ---- Step 2: 定位目标州府 ----
        if not self._navigate_to(target):
            log.error(f"[州府切换] 未找到州府: {target}")
            return False

        # ---- Step 3: 确认弹窗 ----
        if not self._handle_confirm_popup(target):
            log.error("[州府切换] 确认弹窗处理失败")
            return False

        # ---- Step 4: 等待加载 ----
        self._wait_for_loading()

        log.info(f"[州府切换] 成功切换到: {target}")
        return True

    # ----------------------------------------------------------------
    # Step 1: 进入大地图
    # ----------------------------------------------------------------
    def _ensure_on_big_map(self):
        """
        确保当前界面为大地图。

        策略:
          1. 截图 → 检测大地图特征（模板匹配顶部导航栏等）
          2. 如果在 → 直接返回 True
          3. 如果不在 → 点击 big_map_enter_btn → 等待 → 重新检测
          4. 最多重试 3 次

        返回:
          bool: 已在大地图界面为 True。
        """
        enter_btn = self.pref_cfg.get("big_map_enter_btn", {})
        enter_x = enter_btn.get("x", 120)
        enter_y = enter_btn.get("y", 980)

        for attempt in range(3):
            img = ADB.screenshot()
            if img is None:
                log.error("[大地图] 截图失败")
                time.sleep(0.5)
                continue

            # 检测是否已在大地图
            if self._is_on_big_map(img):
                log.info("[大地图] 已在大地图界面")
                return True

            # 点击大地图按钮
            log.info(f"[大地图] 尝试进入 (第{attempt + 1}次)，点击 ({enter_x}, {enter_y})")
            ADB.tap(enter_x, enter_y)
            time.sleep(self.pref_cfg.get("loading_wait", 2.0))

        log.warning("[大地图] 多次尝试后仍未检测到大地图界面，假设已进入")
        return True  # 宽松策略：不因检测失败而卡死

    def _is_on_big_map(self, img):
        """
        检测当前是否在大地图界面。

        检测策略（按优先级）:
          1. 模板匹配：检测预置的大地图特征图（big_map_navbar.png）
          2. 特征点颜色检测：采样 big_map_indicator 坐标的颜色
          3. 行囊按钮检测：搜索行囊按钮特征

        参数:
          img: BGR 格式 numpy 数组。

        返回:
          bool: True 表示当前在大地图。
        """
        # 策略1: 模板匹配大地图特征
        match = self.vision.match_template(img, "big_map_navbar.png")
        if match:
            _, _, conf = match
            log.info(f"[大地图检测] 模板匹配: 置信度 {conf:.2f}")
            return True

        # 策略2: 特征点颜色采样（预留）
        # indicator = self.pref_cfg.get("big_map_indicator", {})
        # px = img[indicator.get("y", 30), indicator.get("x", 960)]
        # ... 颜色比对逻辑

        # 策略3: 行囊按钮存在 = 说明在主地图界面
        match_bag = self.vision.match_template(img, "travel_bag_btn.png")
        if match_bag:
            _, _, conf = match_bag
            log.info(f"[大地图检测] 检测到行囊按钮: 置信度 {conf:.2f}")
            return True

        return False

    # ----------------------------------------------------------------
    # Step 2: 定位目标州府
    # ----------------------------------------------------------------
    def _navigate_to(self, target):
        """
        在大地图上定位并点击目标州府。

        模式分发:
          - mode="coordinate"  → _try_coordinate_mode()
          - mode="template"    → _try_template_search()
          - mode="mser"        → _try_mser_search() (预留)

        参数:
          target: str，目标州府名称。

        返回:
          bool: 成功定位并点击为 True。
        """
        pref_info = self.pref_cfg.get("prefectures", {}).get(target)
        if pref_info is None:
            log.error(f"[定位] 未找到州府配置: {target}，请在 config.json prefecture.prefectures 中添加")
            return False

        if self.mode == "coordinate":
            return self._try_coordinate_mode(target, pref_info)
        elif self.mode == "template":
            return self._try_template_search(target, pref_info)
        elif self.mode == "mser":
            return self._try_mser_search(target, pref_info)
        else:
            log.error(f"[定位] 未知模式: {self.mode}")
            return False

    # ================================================================
    # Mode 1: 坐标直点
    # ================================================================
    def _try_coordinate_mode(self, target, pref_info):
        """
        使用预配置坐标直接点击州府标记。

        流程:
          1. 读取 map_coord 坐标
          2. 若未配置 → 报错并返回 False
          3. 执行点击 → 延时 → 返回 True

        参数:
          target: str，州府名称。
          pref_info: dict，州府的配置信息。

        返回:
          bool: 点击成功为 True。
        """
        coord = pref_info.get("map_coord", {})
        px, py = coord.get("x", 0), coord.get("y", 0)

        if px == 0 and py == 0:
            log.error(
                f"[坐标模式] 州府 '{target}' 未配置 map_coord！\n"
                f"  请在大地图截图中获取坐标后填入 config.json"
                f" → prefecture.prefectures.{target}.map_coord"
            )
            return False

        log.info(f"[坐标模式] 点击州府 '{target}' 坐标 ({px}, {py})")
        ADB.tap(px, py)
        time.sleep(self.cfg["timing"]["popup_wait"])
        return True

    # ================================================================
    # Mode 2: 模板匹配 + 滑动搜索
    # ================================================================
    def _try_template_search(self, target, pref_info):
        """
        使用模板匹配在大地图中搜索目标州府标记。

        搜索策略:
          1. 截图 → 裁剪搜索区域
          2. 遍历 search_templates 列表，逐个模板匹配
          3. 找到 → 点击中心坐标 → 返回 True
          4. 未找到 → 按 directions 顺序滑动地图 → 重新搜索
          5. 超过 max_swipes 次仍未找到 → 返回 False

        参数:
          target: str，州府名称。
          pref_info: dict，州府的配置信息。

        返回:
          bool: 找到并点击为 True。
        """
        search_cfg = self.pref_cfg.get("map_search", {})
        max_swipes = search_cfg.get("max_swipes", 8)
        directions = search_cfg.get("directions", ["up", "down", "left", "right"])
        threshold = search_cfg.get("match_threshold", 0.75)
        roi = self._get_search_roi()

        templates = pref_info.get("search_templates", [])
        if not templates:
            log.error(f"[模板搜索] 州府 '{target}' 未配置 search_templates！")
            return False

        log.info(f"[模板搜索] 开始搜索州府 '{target}'，模板: {templates}")

        for swipe_count in range(max_swipes + 1):
            img = ADB.screenshot()
            if img is None:
                log.error("[模板搜索] 截图失败")
                time.sleep(0.5)
                continue

            # 可选: 裁剪搜索区域减少干扰
            if roi:
                rx, ry, rw, rh = roi
                search_img = img[ry:ry + rh, rx:rx + rw]
            else:
                search_img = img
                rx, ry = 0, 0

            # 遍历所有模板
            for tpl_name in templates:
                match = self.vision.match_template(search_img, tpl_name)
                if match:
                    mx, my, conf = match
                    if conf >= threshold:
                        gx, gy = mx + rx, my + ry
                        log.info(
                            f"[模板搜索] 找到目标! 模板={tpl_name}, "
                            f"坐标=({gx},{gy}), 置信度={conf:.2f}, 滑动次数={swipe_count}"
                        )
                        ADB.tap(gx, gy)
                        time.sleep(self.cfg["timing"]["popup_wait"])
                        return True

            # 未找到，滑动地图
            if swipe_count < max_swipes:
                direction = directions[swipe_count % len(directions)]
                distance = search_cfg.get("swipe_distance", 300)
                log.info(
                    f"[模板搜索] 未找到，滑动 {direction} "
                    f"({swipe_count + 1}/{max_swipes})"
                )
                self._swipe_map(direction, distance)
                time.sleep(search_cfg.get("swipe_interval", 0.8))

        log.warning(f"[模板搜索] 超过最大滑动次数 ({max_swipes})，未找到州府 '{target}'")
        return False

    # ================================================================
    # Mode 3: MSER 文字检测 (预留)
    # ================================================================
    def _try_mser_search(self, target, pref_info):
        """
        使用 MSER 文字区域检测 + OCR 在大地图中搜索目标州府名称。

        当前为占位实现，完整实现需要:
          1. pytesseract 或 paddleocr 库
          2. 或使用游戏内置的文字识别 API

        参数:
          target: str，州府名称。
          pref_info: dict，州府的配置信息。

        返回:
          bool: 找到并点击为 True。
        """
        log.warning(
            f"[MSER模式] 文字检测模式暂未完整实现，"
            f"需要安装 OCR 库 (pip install pytesseract 或 paddleocr)\n"
            f"  当前请使用 coordinate 或 template 模式。"
        )

        # ---- 框架代码（预留） ----
        # img = ADB.screenshot()
        # if img is None:
        #     return False
        #
        # roi = self._get_search_roi()
        # regions = self.vision.find_text_regions(img, roi=roi)
        #
        # for x, y, w, h in regions:
        #     crop = img[y:y + h, x:x + w]
        #     text = ocr(crop)  # 需要 pytesseract / paddleocr
        #     if target in text:
        #         ADB.tap(x + w // 2, y + h // 2)
        #         time.sleep(self.cfg["timing"]["popup_wait"])
        #         return True

        return False

    # ----------------------------------------------------------------
    # 辅助: 获取搜索区域 ROI
    # ----------------------------------------------------------------
    def _get_search_roi(self):
        """
        获取大地图的搜索裁剪区域。

        从 config.json → prefecture.map_search.search_area 读取。
        裁剪是为了排除顶部/底部 UI 按钮，减少误匹配。

        返回:
          tuple | None: (x, y, w, h) 或 None（不裁剪）。
        """
        area = self.pref_cfg.get("map_search", {}).get("search_area")
        if area and area.get("w", 0) > 0 and area.get("h", 0) > 0:
            return (area["x"], area["y"], area["w"], area["h"])
        return None

    # ----------------------------------------------------------------
    # Step 3: 处理确认弹窗
    # ----------------------------------------------------------------
    def _handle_confirm_popup(self, target):
        """
        处理"确认进入州府"弹窗。

        游戏点击州府标记后会弹出确认对话框，需要点击"确认"按钮。

        检测策略（按优先级）:
          1. 模板匹配 confirm_popup.png
          2. 红色按钮检测 (Vision.find_red_buttons)
          3. 使用配置的 confirm_btn 坐标直接点击

        参数:
          target: str，州府名称。

        返回:
          bool: 确认成功（或无需确认）为 True。
        """
        # 获取该州府的确认按钮坐标（优先用专属配置，回退到默认）
        pref_info = self.pref_cfg.get("prefectures", {}).get(target, {})
        confirm_btn = pref_info.get("confirm_btn")
        if confirm_btn is None:
            confirm_btn = self.pref_cfg.get("default_confirm_btn", {})
        confirm_x = confirm_btn.get("x", 960)
        confirm_y = confirm_btn.get("y", 600)

        max_attempts = 5
        for attempt in range(max_attempts):
            img = ADB.screenshot()
            if img is None:
                time.sleep(0.3)
                continue

            # 策略1: 模板匹配确认弹窗
            popup = self.vision.detect_popup(img)
            if popup and popup["type"] in ("confirm", "success"):
                log.info(f"[确认弹窗] 检测到弹窗: {popup['type']}")
                ADB.tap(popup["x"], popup["y"])
                time.sleep(self.cfg["timing"]["popup_wait"])
                return True

            # 策略2: 红色按钮检测
            red_btns = self.vision.find_red_buttons(img)
            if red_btns:
                bx, by, _, _, area = red_btns[0]
                log.info(f"[确认弹窗] 检测到红色按钮: ({bx},{by}), 面积={area:.0f}")
                ADB.tap(bx, by)
                time.sleep(self.cfg["timing"]["popup_wait"])
                return True

            # 策略3: 直接点击确认坐标
            if attempt == 0:
                log.info(f"[确认弹窗] 直接点击确认坐标 ({confirm_x}, {confirm_y})")
                ADB.tap(confirm_x, confirm_y)
            elif attempt < max_attempts - 1:
                log.info(f"[确认弹窗] 重试 ({attempt + 1}/{max_attempts})")
                ADB.tap(confirm_x, confirm_y)

            time.sleep(self.cfg["timing"]["popup_wait"])

        log.warning("[确认弹窗] 多次尝试后仍未检测到确认弹窗")
        return True  # 宽松策略：可能已经进入

    # ----------------------------------------------------------------
    # Step 4: 等待加载
    # ----------------------------------------------------------------
    def _wait_for_loading(self):
        """
        等待城镇界面加载完成。

        策略:
          1. 延时 loading_wait 秒（基础等待）
          2. 轮询检测城镇界面特征（预留）
          3. 最长等待 15 秒后超时退出

        城镇加载特征（预留检测逻辑）:
          - 屏幕底部出现建筑/功能按钮
          - 顶部出现城镇名称
          - 出现"返回大地图"按钮
        """
        loading_wait = self.pref_cfg.get("loading_wait", 3.0)
        log.info(f"[加载] 等待城镇界面加载 ({loading_wait}s)...")
        time.sleep(loading_wait)

        # 轮询检测城镇特征（预留，需要模板截图）
        # max_wait = 15.0
        # start_time = time.time()
        # while time.time() - start_time < max_wait:
        #     img = ADB.screenshot()
        #     if img is not None and self._is_town_loaded(img):
        #         log.info("[加载] 城镇界面已加载")
        #         return True
        #     time.sleep(1.5)

        log.info("[加载] 加载等待完成")

    def _is_town_loaded(self, img):
        """
        检测城镇界面是否已加载完成（预留）。

        检测策略:
          - 模板匹配 town_ui_bottom.png（底部导航栏）
          - 模板匹配 back_to_map_btn.png（返回大地图按钮）
          - 屏幕亮度变化检测

        参数:
          img: BGR 格式 numpy 数组。

        返回:
          bool: True 表示城镇已加载。
        """
        # 预留：检测底部 UI 或返回按钮
        # match = self.vision.match_template(img, "town_bottom_nav.png")
        # return match is not None
        return True  # 当前仅依赖延时

    # ----------------------------------------------------------------
    # 大地图辅助: 滑动操作
    # ----------------------------------------------------------------
    def _swipe_map(self, direction="up", distance=300):
        """
        在大地图上按指定方向滑动。

        参数:
          direction: str，"up" / "down" / "left" / "right"。
          distance: int，滑动像素距离。
        """
        w = self.cfg["screen"]["width"]
        h = self.cfg["screen"]["height"]
        cx, cy = w // 2, h // 2

        if direction == "up":
            ADB.swipe(cx, cy + distance // 2, cx, cy - distance // 2)
        elif direction == "down":
            ADB.swipe(cx, cy - distance // 2, cx, cy + distance // 2)
        elif direction == "left":
            ADB.swipe(cx + distance // 2, cy, cx - distance // 2, cy)
        elif direction == "right":
            ADB.swipe(cx - distance // 2, cy, cx + distance // 2, cy)
        else:
            log.warning(f"[滑动] 未知方向: {direction}，视为向上")
            ADB.swipe(cx, cy + distance // 2, cx, cy - distance // 2)

    # ----------------------------------------------------------------
    # 诊断工具: 坐标获取辅助
    # ----------------------------------------------------------------
    def diagnose(self, save_path=None):
        """
        诊断模式：截图并保存，帮助用户获取州府坐标。

        用法:
          sw = PrefectureSwitcher()
          sw.diagnose()  # 截图保存到 screenshots/ 目录
          # 用户用图片查看器打开截图，获取目标坐标
          # 然后填入 config.json → prefecture.prefectures.<name>.map_coord

        参数:
          save_path: str | None，保存路径。None 时自动生成。
        """
        if save_path is None:
            save_path = str(SCREENSHOT_DIR / "big_map_diagnose.png")

        img = ADB.screenshot(save_path=save_path)
        if img is not None:
            h, w = img.shape[:2]
            log.info(
                f"[诊断] 截图已保存: {save_path} (分辨率: {w}x{h})\n"
                f"  请用图片查看器打开该截图，找到目标州府位置，\n"
                f"  记录其坐标(x,y)并填入 config.json。"
            )
        else:
            log.error("[诊断] 截图失败，请检查 ADB 连接")

        return save_path


# ================================================================
# 模块入口函数（供 launcher.py 调用）
# ================================================================
def run_prefecture_switch(target=None):
    """
    执行州府切换（命令行入口）。

    参数:
      target: str | None，目标州府名称。None 使用配置默认值。

    返回:
      bool: 成功为 True。
    """
    sw = PrefectureSwitcher()
    return sw.switch_to(target)


def run_diagnose():
    """执行诊断模式（截图保存）。"""
    sw = PrefectureSwitcher()
    sw.diagnose()
