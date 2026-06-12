"""
视觉识别模块
~~~~~~~~~~~~

封装所有图像分析逻辑，是钓鱼自动化和将来地图/行囊功能的基础。

主要功能：
  1. 光珠定位（find_bead_on_disc）
        → 灰度阈值 + 环形掩码 + 圆形度 + 轨道距离，共 5 层过滤
  2. 区域判定（which_zone）
        → 根据光珠角度判断当前在蓝区/黄区/无效区
  3. 圆盘可见性检测（is_disc_visible）
        → 采样圆盘区域亮度均值和标准差
  4. 模板匹配（match_template / detect_popup）
        → 用 cv2.matchTemplate 识别已知弹窗图片
  5. 红色按钮检测（find_red_buttons）★ v4.0 新增
        → HSV 颜色空间两段红色范围，用于大地图/行囊确认按钮
  6. 文字区域检测（find_text_regions）★ v4.0 新增
        → MSER 算法，用于匹配城镇/州府名称

注意事项：
  - 光珠颜色偏暖（BGR≈174,242,250），不是纯白，
    因此使用灰度阈值法而非 RGB 等值检测。
  - 所有方法均接收 numpy BGR 数组（来自 ADB.screenshot()），
    返回简单数据类型（tuple / list / str / bool）。
"""

import math
import logging
import numpy as np
import cv2

from .paths import TEMPLATE_DIR

log = logging.getLogger("Common.Vision")


class Vision:
    """
    视觉识别模块：封装所有图像分析逻辑。

    主要职责：
      1. 光珠定位（find_bead_on_disc）：基于灰度阈值 + 几何约束
      2. 区域判定（which_zone）：根据光珠角度判断蓝/黄/无效区
      3. 圆盘可见性检测（is_disc_visible）：采样圆盘区域亮度
      4. 模板匹配（match_template / detect_popup）：识别已知弹窗
      5. 红色按钮检测（find_red_buttons）：HSV 颜色空间提取红色区域
      6. 文字区域检测（find_text_regions）：MSER 算法提取文字候选区

    注意事项：
      - 光珠颜色偏暖（BGR≈174,242,250），不是纯白，
        因此使用灰度阈值而非 RGB 等值检测。
    """

    def __init__(self, cfg):
        """用配置字典初始化所有阈值和坐标参数。"""
        self.cfg = cfg
        self.disc = cfg["disc"]
        self.zones = cfg["zones"]
        self.det = cfg["detection"]

    # ================================================================
    # 光珠检测（v3.1 增强版 — 核心算法）
    # ================================================================
    def find_bead_on_disc(self, img):
        """
        在截图 img 中定位光珠的精确位置。

        算法策略（5 层过滤）：
          Step 1 — 环形掩码：
                  以圆盘中心 (cx,cy) 为圆心，内半径 (bead_r - track_tol)、
                  外半径 (bead_r + track_tol) 创建环形掩码，
                  只保留光珠轨道环带内的像素，过滤轨道外所有 UI 噪声。
          Step 2 — 灰度阈值二值化：
                  光珠亮度（灰度 ~237）远高于轨道/背景（灰度 < 180），
                  用 cv2.THRESH_BINARY 提取亮色候选区域。
          Step 3 — 轮廓查找 + 面积初筛：
                  用 cv2.findContours 找出所有白色连通区域，
                  面积必须在 [bead_min_area, bead_max_area] 范围内。
          Step 4 — 圆形度 + 轨道距离双重校验：
                  圆形度 = 4π·面积 / 周长²（光珠 ≈ 0.7~0.9），
                  距离轨道中心误差必须 < track_tol（默认 20px）。
          Step 5 — 综合打分选取最佳候选：
                  score = 圆形度 × 轨道贴合度 × log1p(面积)，
                  取分数最高的轮廓作为光珠。

        为什么不用 RGB 等值检测？
          → 光珠 BGR = (174, 242, 250)，偏暖色调，R/G/B 三者不相等，
            等值检测（R≈G≈B）会漏检。灰度阈值法更稳定。

        参数：
          img: BGR 格式 numpy 数组（来自 ADB.screenshot()）

        返回：
          (angle, found)
            angle: 光珠角度（度，[0, 360)），0°=正上方，顺时针增加
            found: bool，是否检测到光珠
        """
        h, w = img.shape[:2]
        cx, cy = self.disc["center_x"], self.disc["center_y"]
        bead_r = self.disc["bead_radius"]
        brightness_min = self.det["bead_brightness_min"]
        min_area = self.det["bead_min_area"]
        max_area = self.det["bead_max_area"]
        circ_min = self.det.get("bead_circularity_min", 0.55)
        track_tol = self.det.get("bead_track_tolerance", 20)

        # ---- Step 1: 创建紧贴光珠轨道的环形掩码 ----
        #     只保留圆环区域内的像素，大幅减少误检
        mask = np.zeros((h, w), dtype=np.uint8)
        inner_r = max(1, bead_r - track_tol)
        outer_r_mask = bead_r + track_tol
        cv2.circle(mask, (cx, cy), outer_r_mask, 255, -1)
        cv2.circle(mask, (cx, cy), inner_r, 0, -1)

        # ---- Step 2: 灰度亮度阈值二值化 ----
        #     光珠亮度 >> 其他 UI 元素，用固定阈值即可稳定提取
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, brightness_min, 255, cv2.THRESH_BINARY)
        thresh = cv2.bitwise_and(thresh, thresh, mask=mask)

        # ---- Step 3: 轮廓查找 + 多维度筛选 + 打分 ----
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best_candidate = None
        best_score = -1.0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue

            M = cv2.moments(cnt)
            if M["m00"] <= 0:
                continue

            bx = int(M["m10"] / M["m00"])
            by = int(M["m01"] / M["m00"])
            dx, dy = bx - cx, by - cy
            dist = math.hypot(dx, dy)

            # 轨道距离校验：光珠必须距离轨道中心约 bead_r 像素
            track_err = abs(dist - bead_r)
            if track_err > track_tol:
                continue

            # 圆形度校验：光珠是圆形，不规则碎片会被过滤
            perimeter = cv2.arcLength(cnt, True)
            if perimeter <= 0:
                continue
            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
            if circularity < circ_min:
                continue

            # 综合打分：圆形度高的优先，轨道贴合度高的优先
            track_score = 1.0 - (track_err / track_tol)
            score = circularity * track_score * math.log1p(area)

            if score > best_score:
                best_score = score
                best_candidate = (bx, by, area, circularity, track_err)

        if best_candidate is not None:
            bx, by, area, circ, terr = best_candidate
            dx, dy = bx - cx, by - cy
            # 计算角度：atan2(dx, -dy) 使 0° = 正上方，顺时针增加
            rad = math.atan2(dx, -dy)
            if rad < 0:
                rad += 2 * math.pi
            deg = math.degrees(rad)
            return deg, True
        return 0.0, False

    # ================================================================
    # 区域判定
    # ================================================================
    def which_zone(self, angle):
        """
        根据光珠角度判断所在区域。

        角度定义：0°=正上方，顺时针增加（与游戏内圆盘方向一致）。
        区域范围从 config.json 的 zones 配置读取，支持跨 0° 环绕
        （例如蓝区 300°~60°，即 yellow_end=360, blue_start=0）。

        参数：
          angle: float，光珠角度（度，[0, 360)）

        返回：
          str: "yellow"（黄区/暴击区）、"blue"（蓝区/安全区）、"none"（无效区域）
        """
        ys, ye = self.zones["yellow_start"], self.zones["yellow_end"]
        bs, be = self.zones["blue_start"], self.zones["blue_end"]

        def in_range(a, s, e):
            """角度范围判断，支持跨 0° 环绕（如 300°~60°）。"""
            if s <= e:
                return s <= a <= e
            else:
                return a >= s or a <= e

        if in_range(angle, ys, ye):
            return "yellow"
        if in_range(angle, bs, be):
            return "blue"
        return "none"

    # ================================================================
    # Disc 可见性检测
    # ================================================================
    def is_disc_visible(self, img):
        """
        检测收杆圆盘是否仍显示在屏幕上。

        判定逻辑：
          采样以圆盘中心为原点、outer_radius 为半径的矩形区域，
          计算该区域的灰度均值和标准差。
          - 均值过低（< 60）→ 圆盘已消失（黑屏或无关界面）
          - 标准差过低（< 15）→ 区域颜色单一（无圆盘纹理）

        注意：此方法在 v3.1 后被淡化成辅助手段，
        主逻辑改用 bead_miss_count + disc_lost_timeout 判定。

        参数：
          img: BGR 格式 numpy 数组

        返回：
          bool: True=圆盘可见，False=圆盘消失
        """
        cx, cy = self.disc["center_x"], self.disc["center_y"]
        outer_r = self.disc["outer_radius"]
        h, w = img.shape[:2]

        x1 = max(0, cx - outer_r)
        x2 = min(w, cx + outer_r)
        y1 = max(0, cy - outer_r)
        y2 = min(h, cy + outer_r)

        if x2 <= x1 or y2 <= y1:
            return False

        disc_region = img[y1:y2, x1:x2]
        if disc_region.size == 0:
            return False

        gray = cv2.cvtColor(disc_region, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)

        if mean_brightness < 60 or std_brightness < 15:
            return False
        return True

    # ================================================================
    # 模板匹配
    # ================================================================
    def match_template(self, img, template_name):
        """
        在截图 img 中搜索指定模板图片。

        使用 cv2.TM_CCOEFF_NORMED（归一化相关系数匹配），
        返回值范围 [0, 1]，>= match_threshold 视为匹配成功。

        参数：
          img: BGR 格式 numpy 数组（截图）
          template_name: str，模板文件名（位于 templates/ 目录）

        返回：
          (x, y, confidence) | None
            x, y: 模板中心坐标（int）
            confidence: 匹配置信度（float）
            未找到返回 None
        """
        template_path = TEMPLATE_DIR / template_name
        if not template_path.exists():
            return None
        template = cv2.imread(str(template_path))
        if template is None:
            return None
        result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val >= self.det["match_threshold"]:
            h, w = template.shape[:2]
            cx = max_loc[0] + w // 2
            cy = max_loc[1] + h // 2
            return cx, cy, max_val
        return None

    # ================================================================
    # 弹窗检测
    # ================================================================
    def detect_popup(self, img):
        """
        遍历预定义模板列表，检测屏幕上是否出现已知弹窗。

        检测的弹窗类型（按 templates 列表顺序）：
          - success_popup.png  → "success"（钓鱼成功）
          - failure_popup.png  → "failure"（钓鱼失败）
          - close_btn.png       → "close"（通用关闭按钮）
          - confirm_btn.png     → "confirm"（通用确认按钮）
          - start_fishing_btn.png → "start_fishing"（开始钓鱼按钮）

        参数：
          img: BGR 格式 numpy 数组

        返回：
          dict | None: {"type": str, "x": int, "y": int}
            未检测到返回 None
        """
        templates = [
            ("success_popup.png", "success"),
            ("failure_popup.png", "failure"),
            ("close_btn.png", "close"),
            ("confirm_btn.png", "confirm"),
            ("start_fishing_btn.png", "start_fishing"),
        ]
        for fname, ptype in templates:
            ret = self.match_template(img, fname)
            if ret:
                x, y, conf = ret
                log.info(f"检测到弹窗: {ptype}, 置信度={conf:.2f}, 坐标=({x},{y})")
                return {"type": ptype, "x": x, "y": y}
        return None

    # ================================================================
    # ★ v4.0 新增：红色按钮定位（用于大地图/行囊中的确认按钮）
    # ================================================================
    def find_red_buttons(self, img):
        """
        在截图 img 中检测所有红色按钮区域。

        算法步骤：
          1. BGR → HSV 颜色空间（对红色检测更鲁棒）
          2. 红色在 HSV 中跨 0°（红→深红），需两段范围合并：
             - 低段：[0, 80, 80] ~ [12, 255, 255]
             - 高段：[170, 80, 80] ~ [180, 255, 255]
          3. 形态学闭运算（MORPH_CLOSE）连接红色区域的碎片
          4. 查找轮廓，过滤面积 < 100 的噪声
          5. 返回按面积降序排列的按钮中心坐标列表

        用途：v4.0 新增，用于大地图/行囊中定位确认按钮。
        注意：返回列表包含面积信息，调用方可按面积优先选取主按钮。

        参数：
          img: BGR 格式 numpy 数组

        返回：
          list: [(cx, cy, w, h, area), ...] 按面积降序排列
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # 红色 HSV 范围（两段合并）
        lower_red1 = np.array([0, 80, 80])
        upper_red1 = np.array([12, 255, 255])
        lower_red2 = np.array([170, 80, 80])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        mask = cv2.bitwise_or(mask1, mask2)

        # 形态学闭合，连接碎片
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        buttons = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 100:  # 过小过滤
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            cx = x + w // 2
            cy = y + h // 2
            buttons.append((cx, cy, w, h, area))
        buttons.sort(key=lambda b: b[4], reverse=True)
        return buttons

    # ================================================================
    # ★ v4.1 增强：文字区域检测（游戏 UI 优化版）
    # ================================================================
    def find_text_regions(self, img, roi=None, color_filter=True):
        """
        在截图 img 中检测文字区域（MSER + 颜色/形状过滤）。

        算法增强（v4.1）：
          1. 双相 MSER 检测（正相 + 反相），覆盖浅/深色文字
          2. 颜色过滤：只保留亮色文字区域（游戏 UI 中文字多为白/黄色）
          3. 宽高比过滤：针对中文 2-4 字名横向排列优化
          4. 重叠区域合并（NMS 简化版）

        MSER（最大稳定极值区域）是一种传统的文字检测算法，
        对字体、大小、颜色变化具有一定鲁棒性。
        适用于：游戏 UI 中定位城镇名称、州府名称等文字标签。

        参数：
          img: BGR 格式 numpy 数组
          roi: tuple，可选，(x, y, w, h) 限定检测区域。
              若提供，内部裁剪后检测，返回坐标自动偏移回原图。
          color_filter: bool，是否启用颜色过滤（游戏 UI 亮色文字）。

        返回：
          list: [(x, y, w, h), ...]
            每个 bbox 为（左上X, 左上Y, 宽度, 高度），按从上到下排列
        """
        offset_x, offset_y = 0, 0
        if roi is not None:
            rx, ry, rw, rh = roi
            img = img[ry:ry + rh, rx:rx + rw]
            offset_x, offset_y = rx, ry

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]

        # MSER 检测器（参数针对游戏文字调优）
        mser = cv2.MSER_create(
            delta=3,             # 变化阈值（越小检测越多）
            min_area=40,         # 最小区域（过滤噪声点，比默认 60 小）
            max_area=4000,       # 最大区域（过滤大块背景）
            max_variation=0.25,  # 最大变化率
        )

        # 双相检测：正相（亮文字暗背景）+ 反相（暗文字亮背景）
        regions_pos, _ = mser.detectRegions(gray)
        regions_neg, _ = mser.detectRegions(255 - gray)
        all_regions = list(regions_pos) + list(regions_neg)

        boxes = []
        for region in all_regions:
            pts = region.reshape(-1, 2)
            x, y, rw_box, rh_box = cv2.boundingRect(pts)

            # 尺寸过滤
            if rw_box < 15 or rh_box < 10:
                continue
            if rw_box > 500 or rh_box > 100:
                continue

            # 面积过滤
            area = rw_box * rh_box
            if area < 60 or area > 15000:
                continue

            # 宽高比过滤（针对中文游戏名称）
            # 2字横排 ≈ 2:1 ~ 4:1
            # 3字横排 ≈ 3:1 ~ 6:1
            # 4字横排 ≈ 4:1 ~ 7:1
            aspect = rw_box / max(rh_box, 1)
            if aspect < 1.2 or aspect > 8.0:
                continue

            # 颜色过滤（可选）：游戏 UI 中文字通常为亮色
            if color_filter:
                y1, y2 = max(0, y - 2), min(h, y + rh_box + 2)
                x1, x2 = max(0, x - 2), min(w, x + rw_box + 2)
                roi_patch = img[y1:y2, x1:x2]
                if roi_patch.size > 0:
                    # 采样区域中最亮的像素灰度
                    gray_patch = cv2.cvtColor(roi_patch, cv2.COLOR_BGR2GRAY)
                    bright_pixels = gray_patch[gray_patch > 150]
                    if len(bright_pixels) < area * 0.15:
                        continue  # 亮像素不足 15%，不是文字

            boxes.append((x + offset_x, y + offset_y, rw_box, rh_box))

        # 合并重叠区域
        boxes = self._merge_bboxes(boxes)

        # 按位置排序（从上到下，从左到右）
        boxes.sort(key=lambda b: (b[1] // 30, b[0]))

        return boxes

    def _merge_bboxes(self, bboxes, iou_threshold=0.25):
        """
        合并重叠的边界框（简化 NMS）。

        参数：
          bboxes: [(x, y, w, h), ...]
          iou_threshold: float，IoU 阈值

        返回：
          list: 合并后的 bbox 列表
        """
        if len(bboxes) <= 1:
            return bboxes

        bboxes = sorted(bboxes, key=lambda b: b[0])
        merged = []
        used = [False] * len(bboxes)

        for i, b1 in enumerate(bboxes):
            if used[i]:
                continue
            x1, y1, w1, h1 = b1
            x1e, y1e = x1 + w1, y1 + h1

            for j, b2 in enumerate(bboxes):
                if i == j or used[j]:
                    continue
                x2, y2, w2, h2 = b2
                x2e, y2e = x2 + w2, y2 + h2

                # 计算交集
                ix = max(0, min(x1e, x2e) - max(x1, x2))
                iy = max(0, min(y1e, y2e) - max(y1, y2))
                inter = ix * iy
                union = w1 * h1 + w2 * h2 - inter

                if union > 0 and inter / union > iou_threshold:
                    x1, y1 = min(x1, x2), min(y1, y2)
                    x1e, y1e = max(x1e, x2e), max(y1e, y2e)
                    w1, h1 = x1e - x1, y1e - y1
                    used[j] = True

            merged.append((x1, y1, w1, h1))
            used[i] = True

        return merged
