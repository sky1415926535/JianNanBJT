"""
OCR 文字识别模块 (v4.1)
~~~~~~~~~~~~~~~~~~~~~~~~

为大地图州府切换提供文字识别能力，支持多引擎自动切换。

引擎优先级（自动检测）:
  1. PaddleOCR  — 百度开源，中文识别精度最高，pip 安装
  2. EasyOCR    — 多语言支持，pip 安装，需 PyTorch
  3. MSER-only  — OpenCV 内置，无需额外依赖（仅定位不识别）

特性:
  - 自动检测可用 OCR 引擎，无需手动配置
  - 引擎安装引导（on-demand pip install）
  - 统一的识别接口，对调用方透明
  - 专为游戏 UI 文字优化（浅色文字 + 深色背景）

引擎安装命令:
  # PaddleOCR（推荐，中文精度最高）
  pip install paddlepaddle paddleocr

  # EasyOCR（备选）
  pip install easyocr

  # 若都不装，降级为纯 MSER 区域检测
"""

import logging
import time
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("OCR")

# ----------------------------------------------------------------
# 引擎检测
# ----------------------------------------------------------------
_AVAILABLE_ENGINE = None  # "paddleocr" | "easyocr" | "mser_only"
_OCR_INSTANCE = None


def detect_engine():
    """
    检测当前环境可用的 OCR 引擎。

    检测顺序:
      1. paddleocr (from paddleocr import PaddleOCR)
      2. easyocr (import easyocr)
      3. mser_only（OpenCV 内置，永远可用）

    返回:
      str: "paddleocr" | "easyocr" | "mser_only"
    """
    global _AVAILABLE_ENGINE

    if _AVAILABLE_ENGINE is not None:
        return _AVAILABLE_ENGINE

    # 1. 检测 PaddleOCR
    try:
        from paddleocr import PaddleOCR  # noqa: F401
        _AVAILABLE_ENGINE = "paddleocr"
        log.info("[OCR引擎] 检测到 PaddleOCR")
        return _AVAILABLE_ENGINE
    except ImportError:
        log.debug("[OCR引擎] PaddleOCR 未安装")

    # 2. 检测 EasyOCR
    try:
        import easyocr  # noqa: F401
        _AVAILABLE_ENGINE = "easyocr"
        log.info("[OCR引擎] 检测到 EasyOCR")
        return _AVAILABLE_ENGINE
    except ImportError:
        log.debug("[OCR引擎] EasyOCR 未安装")

    # 3. 降级到 MSER-only
    _AVAILABLE_ENGINE = "mser_only"
    log.info("[OCR引擎] 降级到 MSER-only（无 OCR 库可用）")
    return _AVAILABLE_ENGINE


def get_ocr_install_hint():
    """
    返回 OCR 引擎的安装引导信息。

    返回:
      str: 安装命令提示
    """
    return (
        "\n"
        "  ╔══════════════════════════════════════════════╗\n"
        "  ║  OCR 引擎未安装，文字识别功能受限               ║\n"
        "  ║                                              ║\n"
        "  ║  推荐安装 PaddleOCR（中文精度最高）:           ║\n"
        "  ║    pip install paddlepaddle paddleocr         ║\n"
        "  ║                                              ║\n"
        "  ║  备选 EasyOCR:                                ║\n"
        "  ║    pip install easyocr                        ║\n"
        "  ║                                              ║\n"
        "  ║  当前将使用 MSER 纯区域检测（仅定位不识别）     ║\n"
        "  ╚══════════════════════════════════════════════╝\n"
    )


# ----------------------------------------------------------------
# OCR 统一接口
# ----------------------------------------------------------------
class OCREngine:
    """
    OCR 引擎统一封装。

    使用方式:
      ocr = OCREngine()
      results = ocr.recognize(img)  # → [{"text": "应天府", "bbox": (x,y,w,h), "conf": 0.95}, ...]
    """

    def __init__(self, engine=None):
        """
        初始化 OCR 引擎。

        参数:
          engine: str | None，强制指定引擎。
                  None=自动检测，可选: "paddleocr" / "easyocr" / "mser_only"
        """
        self.engine_name = engine or detect_engine()
        self._impl = None
        self._init_engine()

    def _init_engine(self):
        """根据引擎名初始化对应实现。"""
        if self.engine_name == "paddleocr":
            self._init_paddleocr()
        elif self.engine_name == "easyocr":
            self._init_easyocr()
        else:
            self._init_mser_only()

    def _init_paddleocr(self):
        """初始化 PaddleOCR。"""
        try:
            from paddleocr import PaddleOCR
            self._impl = PaddleOCR(
                use_angle_cls=False,   # 游戏文字通常水平，关闭角度分类加速
                lang="ch",              # 中文
                use_gpu=False,          # CPU 模式
                show_log=False,         # 关闭 PaddleOCR 内部日志
                det_db_thresh=0.2,      # 降低检测阈值（游戏文字可能较小）
                det_db_box_thresh=0.15,
                rec_batch_num=1,
            )
            log.info("[PaddleOCR] 初始化成功 (CPU模式, 中文)")
        except Exception as e:
            log.error(f"[PaddleOCR] 初始化失败: {e}")
            log.warning("[OCR] 降级到 MSER-only")
            self.engine_name = "mser_only"
            self._init_mser_only()

    def _init_easyocr(self):
        """初始化 EasyOCR。"""
        try:
            import easyocr
            self._impl = easyocr.Reader(
                ["ch_sim", "en"],       # 简体中文 + 英文
                gpu=False,
                verbose=False,
            )
            log.info("[EasyOCR] 初始化成功 (CPU模式)")
        except Exception as e:
            log.error(f"[EasyOCR] 初始化失败: {e}")
            log.warning("[OCR] 降级到 MSER-only")
            self.engine_name = "mser_only"
            self._init_mser_only()

    def _init_mser_only(self):
        """初始化 MSER-only 模式（无需额外依赖）。"""
        self._mser = cv2.MSER_create(
            delta=3,           # MSER 变化阈值
            min_area=60,       # 最小区域（过滤噪声点）
            max_area=3000,     # 最大区域（过滤大块背景）
            max_variation=0.3, # 最大变化率
        )
        log.info("[MSER] 初始化成功（仅区域检测，无文字识别）")

    # ----------------------------------------------------------------
    # 识别接口
    # ----------------------------------------------------------------
    def recognize(self, img, roi=None, min_conf=0.5):
        """
        识别 img 中的所有文字区域。

        参数:
          img: BGR 格式 numpy 数组。
          roi: tuple | None，(x, y, w, h) 裁剪区域。None=全图。
          min_conf: float，最低置信度阈值（MSER 模式下忽略）。

        返回:
          list: [{"text": str, "bbox": (x,y,w,h), "center": (cx,cy), "conf": float}, ...]
                按置信度降序排列。
                MSER-only 模式下 text=""，conf=-1。
        """
        # 裁剪 ROI
        if roi:
            rx, ry, rw, rh = roi
            h, w = img.shape[:2]
            ry = max(0, ry)
            rx = max(0, rx)
            rh = min(rh, h - ry)
            rw = min(rw, w - rx)
            crop = img[ry:ry + rh, rx:rx + rw]
        else:
            crop = img
            rx, ry = 0, 0

        # 分发到具体引擎
        if self.engine_name == "paddleocr":
            results = self._recognize_paddleocr(crop, min_conf)
        elif self.engine_name == "easyocr":
            results = self._recognize_easyocr(crop, min_conf)
        else:
            results = self._recognize_mser(crop)

        # 坐标从裁剪区映射回原图
        for r in results:
            bx, by, bw, bh = r["bbox"]
            r["bbox"] = (bx + rx, by + ry, bw, bh)
            r["center"] = (bx + rx + bw // 2, by + ry + bh // 2)

        return results

    def _recognize_paddleocr(self, img, min_conf):
        """PaddleOCR 识别。"""
        results = []
        try:
            ocr_result = self._impl.ocr(img, cls=False)
            if ocr_result and ocr_result[0]:
                for line in ocr_result[0]:
                    box = line[0]          # [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                    text = line[1][0]       # 识别文本
                    conf = line[1][1]       # 置信度

                    if conf < min_conf:
                        continue
                    if not text or not text.strip():
                        continue

                    # 从四点转换到矩形 bbox
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    x, y = int(min(xs)), int(min(ys))
                    w, h = int(max(xs) - x), int(max(ys) - y)

                    results.append({
                        "text": text.strip(),
                        "bbox": (x, y, w, h),
                        "center": (x + w // 2, y + h // 2),
                        "conf": conf,
                    })
        except Exception as e:
            log.error(f"[PaddleOCR] 识别异常: {e}")

        results.sort(key=lambda r: r["conf"], reverse=True)
        return results

    def _recognize_easyocr(self, img, min_conf):
        """EasyOCR 识别。"""
        results = []
        try:
            ocr_results = self._impl.readtext(img)
            for box, text, conf in ocr_results:
                if conf < min_conf:
                    continue
                if not text or not text.strip():
                    continue

                # 四点 → 矩形
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                x, y = int(min(xs)), int(min(ys))
                w, h = int(max(xs) - x), int(max(ys) - y)

                results.append({
                    "text": text.strip(),
                    "bbox": (x, y, w, h),
                    "center": (x + w // 2, y + h // 2),
                    "conf": conf,
                })
        except Exception as e:
            log.error(f"[EasyOCR] 识别异常: {e}")

        results.sort(key=lambda r: r["conf"], reverse=True)
        return results

    def _recognize_mser(self, img):
        """
        MSER 纯区域检测（不识别文字内容）。

        检测原理:
          1. 灰度化
          2. MSER 检测极值区域
          3. 合并重叠区域
          4. 宽高比 + 面积过滤（针对中文游戏文字优化）

        返回的文字区域没有 text（空字符串），仅提供坐标定位。
        调用方需要通过坐标或上下文推断区域含义。
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 正相 + 反相检测（白色文字 + 黑色文字都覆盖）
        regions_all, _ = self._mser.detectRegions(gray)
        regions_inv, _ = self._mser.detectRegions(255 - gray)

        raw_regions = list(regions_all) + list(regions_inv)
        if not raw_regions:
            return []

        # 转为矩形 + 基础过滤
        bboxes = []
        for region in raw_regions:
            xs = region[:, 0]
            ys = region[:, 1]
            x, y = int(min(xs)), int(min(ys))
            w, h = int(max(xs) - x), int(max(ys) - y)

            # 面积过滤
            if w * h < 60 or w * h > 8000:
                continue

            # 宽高比过滤：游戏中文名通常是 2-4 个字，
            #   横向排列 ≈ 3:1 ~ 6:1 (3字约150px宽 x 30px高)
            #   竖排不考虑（大地图文字都是横排）
            aspect = w / max(h, 1)
            if aspect < 1.5 or aspect > 10:
                continue

            # 最小尺寸
            if w < 30 or h < 12:
                continue

            bboxes.append((x, y, w, h))

        # 合并重叠区域（NMS 简化版）
        bboxes = _merge_overlapping_bboxes(bboxes)

        # 按位置排序（从上到下，从左到右）
        bboxes.sort(key=lambda b: (b[1] // 50, b[0]))

        return [
            {
                "text": "",
                "bbox": (x, y, w, h),
                "center": (x + w // 2, y + h // 2),
                "conf": -1.0,
            }
            for x, y, w, h in bboxes
        ]

    # ----------------------------------------------------------------
    # 州府名称搜索
    # ----------------------------------------------------------------
    def find_prefecture(self, img, target_name, roi=None, fuzzy=True):
        """
        在图像中搜索目标州府名称的文字区域。

        搜索策略:
          1. OCR 识别全图文字
          2. 将每个识别结果与目标名称比较
          3. fuzzy=True 时使用模糊匹配（"苏州府" 匹配 "苏州" 也算）
          4. 返回最佳匹配的文字区域中心坐标

        参数:
          img: BGR 格式 numpy 数组。
          target_name: str，目标州府名称（如 "苏州府"）。
          roi: tuple | None，搜索区域的 (x,y,w,h)。
          fuzzy: bool，是否启用模糊匹配。

        返回:
          dict | None: {"center": (cx,cy), "text": str, "conf": float, "bbox": (x,y,w,h)}
                      未找到返回 None。
        """
        results = self.recognize(img, roi=roi, min_conf=0.4)

        if not results:
            log.debug(f"[搜索] 未检测到任何文字区域")
            return None

        # 日志：输出所有识别到的文字（便于调试）
        texts_found = [(r["text"], r["conf"]) for r in results if r["text"]]
        log.debug(f"[搜索] 识别到 {len(texts_found)} 条文字: {texts_found[:10]}")

        # 精确匹配优先
        for r in results:
            if r["text"] == target_name:
                log.info(f"[搜索] 精确匹配: '{target_name}' 置信度={r['conf']:.2f}")
                return r

        # 模糊匹配：目标名称是识别结果的子串，或反之
        if fuzzy:
            for r in results:
                if not r["text"]:
                    continue
                # "苏州府" in "苏州府" 或 "苏州" in "苏州府"
                if target_name in r["text"] or r["text"] in target_name:
                    log.info(
                        f"[搜索] 模糊匹配: 识别='{r['text']}' vs 目标='{target_name}' "
                        f"置信度={r['conf']:.2f}"
                    )
                    return r

        log.debug(f"[搜索] 未找到匹配 '{target_name}' 的文字区域")
        return None

    # ----------------------------------------------------------------
    # MSER 区域汇总（用于无 OCR 时的降级策略）
    # ----------------------------------------------------------------
    def get_all_text_regions(self, img, roi=None):
        """
        获取所有文字候选区域（MSER 检测）。

        用于无 OCR 库时的降级方案：
          - 获取所有文字候选区域
          - 每个区域截图保存，供人工/外部工具识别

        参数:
          img: BGR 格式 numpy 数组。
          roi: tuple | None，搜索区域。

        返回:
          list: [{"bbox": (x,y,w,h), "center": (cx,cy)}, ...]
        """
        if self.engine_name == "mser_only":
            return self.recognize(img, roi=roi)
        else:
            # 有 OCR 引擎时也用 MSER 做辅助检测
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if roi else None
            # ... (简化实现)
            return self.recognize(img, roi=roi)


# ----------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------
def _merge_overlapping_bboxes(bboxes, iou_threshold=0.3):
    """
    合并重叠的边界框（简化 NMS）。

    两个框的 IoU（交并比）> threshold 时，取外接矩形。

    参数:
      bboxes: [(x, y, w, h), ...]
      iou_threshold: float，重叠阈值。

    返回:
      list: 合并后的 bbox 列表。
    """
    if len(bboxes) <= 1:
        return bboxes

    bboxes = sorted(bboxes, key=lambda b: b[0])  # 按 x 排序
    merged = []
    used = [False] * len(bboxes)

    for i, b1 in enumerate(bboxes):
        if used[i]:
            continue
        x1, y1, w1, h1 = b1
        x1_r, y1_r = x1 + w1, y1 + h1

        for j, b2 in enumerate(bboxes):
            if i == j or used[j]:
                continue
            x2, y2, w2, h2 = b2
            x2_r, y2_r = x2 + w2, y2 + h2

            # 计算交集
            inter_x = max(0, min(x1_r, x2_r) - max(x1, x2))
            inter_y = max(0, min(y1_r, y2_r) - max(y1, y2))
            inter_area = inter_x * inter_y
            union_area = w1 * h1 + w2 * h2 - inter_area

            if union_area > 0 and inter_area / union_area > iou_threshold:
                # 合并：取外接矩形
                x1 = min(x1, x2)
                y1 = min(y1, y2)
                x1_r = max(x1_r, x2_r)
                y1_r = max(y1_r, y2_r)
                w1 = x1_r - x1
                h1 = y1_r - y1
                used[j] = True

        merged.append((x1, y1, w1, h1))
        used[i] = True

    return merged


# ================================================================
# 便捷函数
# ================================================================
def create_ocr_engine(engine=None, verbose=True):
    """
    创建 OCR 引擎实例。

    参数:
      engine: str | None，强制指定引擎。None=自动检测。
      verbose: bool，是否打印安装提示。

    返回:
      OCREngine 实例
    """
    actual_engine = engine or detect_engine()
    if actual_engine == "mser_only" and verbose:
        log.info(get_ocr_install_hint())
    return OCREngine(engine=engine)
