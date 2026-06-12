"""
大地图州府切换模块 (v4.1 — OCR 文字识别完整实现)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

功能：在大地图上定位并切换到目标州府。

交互流程（5 步）:
  Step 1 — 进入大地图
           检测当前界面 → 点击大地图按钮 → 等待加载
  Step 2 — 定位州府
           截图 → 三种模式按优先级尝试:
             Mode 1: 坐标直点（最快，需预配置坐标）
             Mode 2: OCR 文字识别 + 滑动搜索（v4.1 完整实现）
             Mode 3: 模板匹配 + 滑动搜索（需模板截图）
  Step 3 — 点击州府标记
           执行 ADB.tap(map_coord)
  Step 4 — 确认弹窗
           检测弹出确认对话框 → 点击"确认"按钮
  Step 5 — 等待加载
           等待城镇界面加载完成

OCR 引擎（v4.1 新增）:
  - 优先级: PaddleOCR → EasyOCR → MSER-only
  - PaddleOCR: 中文精度最高，推荐安装 (pip install paddlepaddle paddleocr)
  - EasyOCR: 备选方案 (pip install easyocr)
  - MSER-only: 仅检测文字区域位置，不识别内容（降级方案）

配置结构 (config.json → prefecture):
  {
    "target": "白雪镇",                    # 默认目标州府
    "mode": "ocr",                         # 定位模式: coordinate / ocr / template
    "mode_order": ["ocr", "coordinate", "template"],  # 模式降级顺序
    "big_map_enter_btn": {"x": N, "y": N}, # 大地图按钮坐标
    "big_map_indicator": {"x": N, "y": N}, # 特征检测点
    "default_confirm_btn": {"x": N, "y": N}, # 通用确认按钮
    "loading_wait": 3.0,                   # 加载等待时间
    "ocr_search": {                        # OCR 文字搜索参数
      "max_swipes": 5,
      "swipe_distance": 250,
      "swipe_interval": 0.8,
      "mins_conf": 0.4,
      "fuzzy_match": true
    },
    "map_search": {                        # 模板匹配搜索参数
      "max_swipes": 8,
      "swipe_distance": 300,
      "swipe_interval": 0.8,
      "directions": ["up","down","left","right"],
      "match_threshold": 0.75,
      "search_area": {"x":200,"y":100,"w":1520,"h":800}
    },
    "prefectures": {                       # 州府列表
      "<name>": {
        "map_coord": {"x": N, "y": N},     # 大地图上的坐标（coordinate 模式用）
        "confirm_btn": {"x": N, "y": N},   # 确认按钮（可选）
        "search_templates": ["xxx.png"],   # 模板匹配用图片
        "aliases": ["苏州", "姑苏"]         # 别名列表（OCR 模糊匹配增强）
      }
    }
  }

所有已知州府（按解锁顺序）:
  应天府(初始), 苏州府(17级), 杭州府(27级), 松江府(37级),
  徽州府(47级), 扬州府(54级), 绍兴府(60级), 白雪镇(DLC)

使用方式:
  python launcher.py switch-prefecture --target 苏州府
  python launcher.py switch-prefecture              # 使用配置默认值
  python launcher.py diagnose-map                   # 坐标诊断模式
"""

import time
import logging
from pathlib import Path

import numpy as np
import cv2

from common import ADB, Vision, load_config, SCREENSHOT_DIR
from common.ocr import OCREngine, detect_engine, get_ocr_install_hint

log = logging.getLogger("MapSwitch")

# 全局 OCR 引擎实例（懒加载，避免重复初始化）
_OCR_ENGINE = None


def _get_ocr(cfg=None):
    """获取全局 OCR 引擎实例（懒加载）。"""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        engine_mode = detect_engine()
        if engine_mode == "mser_only":
            log.warning(get_ocr_install_hint())
        _OCR_ENGINE = OCREngine()
    return _OCR_ENGINE


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
        self.mode = self.pref_cfg.get("mode", "ocr")
        self.vision = Vision(self.cfg)
        self.ocr = _get_ocr(self.cfg)
        self._last_swipe_dir_idx = 0

    # ----------------------------------------------------------------
    # 主入口
    # ----------------------------------------------------------------
    def switch_to(self, target=None, return_to_town=True):
        """
        切换到目标州府（完整流程入口）。

        执行流程:
          1. _ensure_on_big_map()    → 确保在大地图界面
          2. _navigate_to(target)    → 定位并点击目标州府（多模式降级）
          3. _handle_confirm_popup() → 处理确认弹窗
          4. _wait_for_loading()     → 等待城镇加载
          5. _exit_big_map()         → 从大地图返回城镇视图（v4.2新增）

        参数:
          target: str | None，州府名称。None 使用配置中的 target 默认值。
          return_to_town: bool，切换后是否从大地图返回城镇视图（默认 True）。

        返回:
          bool: 切换成功为 True。
        """
        target = target or self.target
        log.info(f"[州府切换] 目标: {target} (主模式: {self.mode}, OCR引擎: {self.ocr.engine_name})")

        # ---- Step 1: 进入大地图 ----
        if not self._ensure_on_big_map():
            log.error("[州府切换] 无法进入大地图界面")
            return False

        # ---- Step 2: 定位目标州府（多模式降级） ----
        if not self._navigate_to(target):
            log.error(f"[州府切换] 所有模式均未找到州府: {target}")
            return False

        # ---- Step 3: 确认弹窗 ----
        if not self._handle_confirm_popup(target):
            log.error("[州府切换] 确认弹窗处理失败")
            return False

        # ---- Step 4: 等待加载 ----
        self._wait_for_loading()

        # ---- Step 5: 从大地图返回城镇视图 ----
        if return_to_town:
            self._exit_big_map()

        log.info(f"[州府切换] 成功切换到: {target}")
        return True

    # ----------------------------------------------------------------
    # Step 1: 进入大地图
    # ----------------------------------------------------------------
    def _ensure_on_big_map(self):
        """
        确保当前界面为大地图。

        两步操作流程（v4.2 更新）:
          1. 点击左下角"州府印"（红色印章）
          2. 等待弹窗出现（~0.5s）
          3. 在弹窗中点击"大地图"按钮
          4. 等待大地图加载

        大地图 vs 城镇视图判定:
          - 城镇视图: 左下角有大面积红色（州府印可见，红色比例 > 25%）
          - 大地图: 左下角红色极少（州府印消失，红色比例 < 10%）

        返回:
          bool: 已在大地图界面为 True。
        """
        enter_btn = self.pref_cfg.get("big_map_enter_btn", {})
        menu_btn = self.pref_cfg.get("big_map_menu_btn", {})
        enter_x = enter_btn.get("x", 108)
        enter_y = enter_btn.get("y", 908)
        menu_x = menu_btn.get("x", 218)
        menu_y = menu_btn.get("y", 389)
        popup_wait = self.pref_cfg.get("popup_wait", 0.5)
        loading_wait = self.pref_cfg.get("loading_wait", 3.0)

        for attempt in range(3):
            img = ADB.screenshot()
            if img is None:
                log.error("[大地图] 截图失败")
                time.sleep(0.5)
                continue

            if self._is_on_big_map(img):
                log.info("[大地图] 已在大地图界面")
                return True

            # ---- 两步点击流程 ----
            # Step A: 点击州府印 → 弹出功能菜单
            log.info(f"[大地图] 第{attempt + 1}次尝试: 点击州府印 ({enter_x}, {enter_y})")
            ADB.tap(enter_x, enter_y)
            time.sleep(popup_wait)

            # Step B: 检测弹窗是否出现，然后点击"大地图"按钮
            img2 = ADB.screenshot()
            if img2 is not None and self._is_popup_open(img2):
                log.info(f"[大地图] 弹窗已打开，点击'大地图'按钮 ({menu_x}, {menu_y})")
            else:
                log.info(f"[大地图] 未检测到弹窗，直接点击'大地图'按钮 ({menu_x}, {menu_y})")

            ADB.tap(menu_x, menu_y)
            time.sleep(loading_wait)

            # 验证是否进入大地图
            img3 = ADB.screenshot()
            if img3 is not None and self._is_on_big_map(img3):
                log.info("[大地图] 已成功进入大地图界面")
                return True

            log.warning(f"[大地图] 第{attempt + 1}次未成功，重试...")

        log.warning("[大地图] 多次尝试后仍未检测到大地图界面，假设已进入")
        return True

    def _exit_big_map(self):
        """
        从大地图返回城镇视图（反向流程）。

        策略:
          按 Android 返回键（已验证有效，红色比例从 ~16% → ~53%）。

        返回:
          bool: 已返回城镇视图为 True。
        """
        log.info("[反向流程] 大地图 → 城镇视图（按 Android 返回键）")
        ADB.press_back()
        time.sleep(self.pref_cfg.get("loading_wait", 2.0))

        # 验证是否返回城镇视图
        img = ADB.screenshot()
        if img is not None and not self._is_on_big_map(img):
            log.info("[反向流程] 已成功返回城镇视图")
            return True

        log.warning("[反向流程] 未能确认返回城镇视图，假设已返回")
        return True

    def _is_popup_open(self, img):
        """
        检测州府印弹窗是否已打开。

        检测策略:
          在弹窗区域（x:60-460, y:140-400）检测红色按钮数量，
          如果有 >= 3 个红色按钮区域则判定弹窗已打开。

        参数:
          img: numpy array，游戏截图。

        返回:
          bool: 弹窗已打开为 True。
        """
        try:
            h, w = img.shape[:2]
            if h < 400 or w < 460:
                return False
            roi = img[140:400, 60:460]

            # 红色像素检测（HSV）
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower1 = np.array([0, 100, 100])
            upper1 = np.array([10, 255, 255])
            lower2 = np.array([160, 100, 100])
            upper2 = np.array([180, 255, 255])
            mask = cv2.bitwise_or(
                cv2.inRange(hsv, lower1, upper1),
                cv2.inRange(hsv, lower2, upper2)
            )

            # 查找红色轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            red_btn_count = 0
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > 100:
                    red_btn_count += 1

            log.debug(f"[弹窗检测] 红色区域数量: {red_btn_count}")
            return red_btn_count >= 3
        except Exception as e:
            log.debug(f"[弹窗检测] 异常: {e}")
            return False

    def _is_on_big_map(self, img):
        """
        检测当前是否在大地图界面。

        检测策略（按优先级）:
          0. 左下角红色比例检测: 城镇视图有州府印（红色比例 > 20%），
             大地图州府印消失（红色比例 < 10%）
          1. 模板匹配：检测预置的大地图特征图
          2. 行囊按钮检测：搜索行囊按钮特征
          3. 文字区域密度检测：大地图上州府名称文字较多

        返回:
          bool: True 表示当前在大地图。
        """
        # ---- 策略0: 左下角红色比例检测（v4.2 新增，最可靠） ----
        h, w = img.shape[:2]
        lb = img[int(h * 0.65):h, 0:int(w * 0.13)]  # 左下角 ~13% 宽度, ~35% 高度

        # 红色像素比例
        try:
            r_channel = lb[:, :, 2].astype(np.float32)
            g_channel = lb[:, :, 1].astype(np.float32)
            b_channel = lb[:, :, 0].astype(np.float32)
            red_mask = (r_channel > 120) & (r_channel > g_channel * 1.2) & (r_channel > b_channel * 1.2)
            red_ratio = np.sum(red_mask) / red_mask.size

            if red_ratio < 0.08:
                log.info(f"[大地图检测] 左下角红色比例={red_ratio:.3f} < 0.08 → 判定为大地图（州府印消失）")
                return True
            elif red_ratio > 0.20:
                log.debug(f"[大地图检测] 左下角红色比例={red_ratio:.3f} > 0.20 → 判定为城镇视图（州府印可见）")
                return False
            # 灰色区域 (0.08 ~ 0.20): 不确定，继续其他策略
            log.debug(f"[大地图检测] 左下角红色比例={red_ratio:.3f} 在灰色区域，继续其他检测...")
        except Exception as e:
            log.debug(f"[大地图检测] 红色比例计算异常: {e}")

        # 策略1: 模板匹配大地图特征
        match = self.vision.match_template(img, "big_map_navbar.png")
        if match:
            _, _, conf = match
            log.info(f"[大地图检测] 模板匹配: 置信度 {conf:.2f}")
            return True

        # 策略2: 行囊按钮存在 = 说明在主地图界面
        match_bag = self.vision.match_template(img, "travel_bag_btn.png")
        if match_bag:
            _, _, conf = match_bag
            log.info(f"[大地图检测] 检测到行囊按钮: 置信度 {conf:.2f}")
            return True

        # 策略3: 文字区域数量检测（大地图上通常有多个州府名称文字）
        # 在大地图中心区域搜索，如果有 >= 2 个文字区域则判定为大地图
        text_regions = self.vision.find_text_regions(
            img,
            roi=(w // 4, h // 4, w // 2, h // 2),
            color_filter=True
        )
        if len(text_regions) >= 2:
            log.info(f"[大地图检测] 检测到 {len(text_regions)} 个文字区域（推测为大地图）")
            return True

        return False

    # ----------------------------------------------------------------
    # Step 2: 定位目标州府（多模式降级）
    # ----------------------------------------------------------------
    def _navigate_to(self, target):
        """
        在大地图上定位并点击目标州府（多模式降级策略）。

        使用 config.json → prefecture.mode_order 定义的模式顺序，
        逐个尝试直到成功。默认顺序: ["ocr", "coordinate", "template"]

        参数:
          target: str，目标州府名称。

        返回:
          bool: 成功定位并点击为 True。
        """
        pref_info = self.pref_cfg.get("prefectures", {}).get(target)
        if pref_info is None:
            log.error(f"[定位] 未找到州府配置: {target}")
            return False

        # 模式降级顺序
        mode_order = self.pref_cfg.get("mode_order", ["ocr", "coordinate", "template"])

        for mode in mode_order:
            log.info(f"[定位] 尝试模式: {mode}")
            if mode == "ocr":
                if self._try_ocr_search(target, pref_info):
                    return True
            elif mode == "coordinate":
                if self._try_coordinate_mode(target, pref_info):
                    return True
            elif mode == "template":
                if self._try_template_search(target, pref_info):
                    return True
            else:
                log.warning(f"[定位] 未知模式: {mode}，跳过")
            log.info(f"[定位] 模式 '{mode}' 未找到，尝试下一个...")

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
                f"  请运行 python launcher.py diagnose-map 获取坐标后填入 config.json"
            )
            return False

        log.info(f"[坐标模式] 点击州府 '{target}' 坐标 ({px}, {py})")
        ADB.tap(px, py)
        time.sleep(self.cfg["timing"]["popup_wait"])
        return True

    # ================================================================
    # Mode 2: OCR 文字识别 + 滑动搜索（v4.1 完整实现）
    # ================================================================
    def _try_ocr_search(self, target, pref_info):
        """
        使用 OCR 文字识别在大地图中搜索目标州府名称。

        这是 v4.1 的核心新增功能。

        搜索策略:
          1. 截图 + 裁剪搜索区域
          2. OCR 识别全图文字 → 匹配目标州府名称
          3. 精确匹配优先，再试模糊匹配（含别名）
          4. 未找到 → 滑动地图 → 重新搜索
          5. 超过 max_swipes 次仍未找到 → 返回 False

        匹配规则:
          - 精确匹配: 识别文本 == 目标名称（如 "苏州府" == "苏州府"）
          - 模糊匹配: 目标名称是识别文本的子串（如 "苏州" in "苏州府"）
          - 别名匹配: pref_info.aliases 中的名称（如 ["姑苏"] 匹配 "姑苏"）

        参数:
          target: str，目标州府名称。
          pref_info: dict，州府的配置信息。

        返回:
          bool: 找到并点击为 True。
        """
        ocr_cfg = self.pref_cfg.get("ocr_search", {})
        max_swipes = ocr_cfg.get("max_swipes", 5)
        swipe_distance = ocr_cfg.get("swipe_distance", 250)
        swipe_interval = ocr_cfg.get("swipe_interval", 0.8)
        min_conf = ocr_cfg.get("min_conf", 0.4)
        fuzzy = ocr_cfg.get("fuzzy_match", True)

        # 构建搜索目标列表（名称 + 别名）
        search_targets = [target]
        aliases = pref_info.get("aliases", [])
        search_targets.extend(aliases)

        # 如果目标以"府"或"镇"结尾，也添加去掉后缀的简短版本
        for suffix in ("府", "镇"):
            if target.endswith(suffix):
                short = target[:-1]  # "苏州府" → "苏州"
                if short not in search_targets:
                    search_targets.append(short)
                break

        log.info(
            f"[OCR搜索] 开始搜索 '{target}' "
            f"(候选: {search_targets}, OCR引擎: {self.ocr.engine_name})"
        )

        # MSER-only 模式禁用滑动搜索告警
        if self.ocr.engine_name == "mser_only":
            log.warning(
                "[OCR搜索] 当前为 MSER-only 模式，只能检测文字区域位置，无法识别文字。\n"
                "  请安装 PaddleOCR 后重试: pip install paddlepaddle paddleocr\n"
                "  或切换到 coordinate/template 模式。"
            )

        # 获取搜索 ROI
        roi = self._get_search_roi()

        for swipe_count in range(max_swipes + 1):
            img = ADB.screenshot()
            if img is None:
                log.error("[OCR搜索] 截图失败")
                time.sleep(0.5)
                continue

            if swipe_count == 0 and self.ocr.engine_name == "mser_only":
                # MSER-only 首轮：输出诊断信息
                regions = self.vision.find_text_regions(
                    img, roi=roi, color_filter=True
                )
                log.info(
                    f"[OCR搜索] MSER 检测到 {len(regions)} 个文字候选区域。"
                    f" 建议: 安装 PaddleOCR 实现文字识别。"
                )
                if regions:
                    # 输出前 5 个区域的坐标（帮助人工判断）
                    sample = regions[:5]
                    log.info(f"[OCR搜索] 候选区域样本: {sample}")
                # MSER-only 不继续，直接跳到滑动
                if swipe_count < max_swipes:
                    self._swipe_map("up", swipe_distance)
                    time.sleep(swipe_interval)
                continue

            # ---- OCR 识别 + 匹配 ----
            for search_name in search_targets:
                result = self.ocr.find_prefecture(
                    img, search_name, roi=roi, fuzzy=fuzzy
                )
                if result:
                    cx, cy = result["center"]
                    matched_text = result["text"]
                    conf = result["conf"]
                    log.info(
                        f"[OCR搜索] ✅ 找到! 识别='{matched_text}' → 目标='{search_name}' "
                        f"坐标=({cx},{cy}) 置信度={conf:.2f} 滑动次数={swipe_count}"
                    )
                    ADB.tap(cx, cy)
                    time.sleep(self.cfg["timing"]["popup_wait"])
                    return True

            # ---- OCR 识别完成但没有匹配 ----
            # 输出识别到的文字列表（便于诊断）
            ocr_results = self.ocr.recognize(img, roi=roi, min_conf=0.3)
            texts = [r["text"] for r in ocr_results if r["text"]]
            if texts:
                log.debug(f"[OCR搜索] 本轮识别到: {texts[:15]}")

            # 未找到 → 滑动地图
            if swipe_count < max_swipes:
                directions = ["up", "left", "down", "right"]
                direction = directions[swipe_count % len(directions)]
                log.info(
                    f"[OCR搜索] 未找到，滑动 {direction} "
                    f"({swipe_count + 1}/{max_swipes})"
                )
                self._swipe_map(direction, swipe_distance)
                time.sleep(swipe_interval)

        log.warning(f"[OCR搜索] 超过最大滑动次数 ({max_swipes})，未找到州府 '{target}'")
        return False

    # ================================================================
    # Mode 3: 模板匹配 + 滑动搜索
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

            if roi:
                rx, ry, rw, rh = roi
                search_img = img[ry:ry + rh, rx:rx + rw]
            else:
                search_img = img
                rx, ry = 0, 0

            for tpl_name in templates:
                match = self.vision.match_template(search_img, tpl_name)
                if match:
                    mx, my, conf = match
                    if conf >= threshold:
                        gx, gy = mx + rx, my + ry
                        log.info(
                            f"[模板搜索] 找到目标! 模板={tpl_name}, "
                            f"坐标=({gx},{gy}), 置信度={conf:.2f}, 滑动={swipe_count}"
                        )
                        ADB.tap(gx, gy)
                        time.sleep(self.cfg["timing"]["popup_wait"])
                        return True

            if swipe_count < max_swipes:
                direction = directions[swipe_count % len(directions)]
                distance = search_cfg.get("swipe_distance", 300)
                log.info(f"[模板搜索] 未找到，滑动 {direction} ({swipe_count + 1}/{max_swipes})")
                self._swipe_map(direction, distance)
                time.sleep(search_cfg.get("swipe_interval", 0.8))

        log.warning(f"[模板搜索] 超过最大滑动次数 ({max_swipes})，未找到州府 '{target}'")
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
        return True

    # ----------------------------------------------------------------
    # Step 4: 等待加载
    # ----------------------------------------------------------------
    def _wait_for_loading(self):
        """
        等待城镇界面加载完成。

        策略:
          1. 延时 loading_wait 秒（基础等待）
          2. 轮询检测城镇界面特征（预留）
        """
        loading_wait = self.pref_cfg.get("loading_wait", 3.0)
        log.info(f"[加载] 等待城镇界面加载 ({loading_wait}s)...")
        time.sleep(loading_wait)
        log.info("[加载] 加载等待完成")

    def _is_town_loaded(self, img):
        """检测城镇界面是否已加载完成（预留）。"""
        return True

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
            log.warning(f"[滑动] 未知方向: {direction}")
            ADB.swipe(cx, cy + distance // 2, cx, cy - distance // 2)

    # ----------------------------------------------------------------
    # 诊断工具: 坐标获取辅助
    # ----------------------------------------------------------------
    def diagnose(self, save_path=None):
        """
        诊断模式：截图并保存，同时输出 MSER 文字区域检测结果。

        用法:
          sw = PrefectureSwitcher()
          sw.diagnose()  # 截图 + 文字区域检测 + OCR 识别（如果有 OCR 引擎）

        参数:
          save_path: str | None，保存路径。None 时自动生成。
        """
        if save_path is None:
            save_path = str(SCREENSHOT_DIR / "big_map_diagnose.png")

        img = ADB.screenshot(save_path=save_path)
        if img is None:
            log.error("[诊断] 截图失败，请检查 ADB 连接")
            return save_path

        h, w = img.shape[:2]
        log.info(f"[诊断] 截图已保存: {save_path} (分辨率: {w}x{h})")

        # MSER 文字区域检测
        roi = self._get_search_roi()
        regions = self.vision.find_text_regions(img, roi=roi, color_filter=True)
        log.info(f"[诊断] MSER 检测到 {len(regions)} 个文字候选区域:")
        for i, (x, y, rw, rh) in enumerate(regions[:15]):
            log.info(f"  [{i}] ({x}, {y}) {rw}x{rh}")

        # OCR 识别（如果有可用引擎）
        if self.ocr.engine_name != "mser_only":
            log.info(f"[诊断] 使用 {self.ocr.engine_name} 进行 OCR 识别...")
            results = self.ocr.recognize(img, roi=roi, min_conf=0.3)
            texts = [(r["text"], r["conf"], r["center"]) for r in results if r["text"]]
            log.info(f"[诊断] OCR 识别到 {len(texts)} 条文字:")
            for text, conf, center in texts[:20]:
                log.info(f"  '{text}' 置信度={conf:.2f} 坐标={center}")
        else:
            log.info(
                "[诊断] 无 OCR 引擎，仅输出文字区域坐标。\n"
                "  安装 PaddleOCR 后可自动识别文字: pip install paddlepaddle paddleocr"
            )

        log.info(
            f"\n[诊断] 请参照上述坐标，在 config.json 中配置州府信息:\n"
            f"  prefecture.prefectures.<州府名>.map_coord = {{\"x\": X, \"y\": Y}}"
        )

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
    """执行诊断模式（截图 + OCR 分析）。"""
    sw = PrefectureSwitcher()
    sw.diagnose()
