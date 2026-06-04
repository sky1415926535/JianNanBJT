"""
================================================================================
江南百景图 白雪镇 钓鱼自动化脚本 (v3.2)
================================================================================
环境：雷电模拟器9 + ADB + Python + OpenCV
运行平台：Windows（雷电模拟器 ADB 路径自动检测）

【v3.2 更新说明】（新增 retry 模式 + 无响应超时退出）
  1. ★ 新增 `retry` 子命令：从结果页「再来一次」按钮开始执行
  2. ★ 60秒无响应自动退出：基于 last_click_time + last_bead_time 双时间戳
  3. ★ 超时通知：写 alert.txt 文件 + Windows 弹窗通知
  4. ★ 移除对 _touch_activity() 的依赖，避免 Edit 工具匹配问题

【v3.1 更新说明】（修复 ROUND_OVER 死循环 Bug）
  1. ★ 连续未检测计数：需连续 N 次未检测到光珠才判定结束
  2. ★ 消失超时延长：从 2.5s → 4.0s，减少暗区误判
  3. ★ ROUND_OVER 逻辑修复：用光珠检测（而非 disc 可见性）确认结果页
  4. ★ 移除死循环根因：ROUND_OVER 不再因 disc 可见而切回 FISHING

【v3.0 更新说明】
  1. ★ 收杆检测：追踪光珠消失时间，判定钓鱼结束（不再依赖模板匹配）
  2. ★ 再来一次：钓鱼结束后自动点击「收杆/领取」→「再来一次」循环
  3. 截图稳定性增强：使用唯一文件名避免写入冲突
  4. 点击逻辑优化：光珠在有效区域时持续点击（不再依赖"新进入"）
  5. 失败重试机制：支持配置重试开关和最大次数
  6. Disc 可见性检测：确认结果页/disc 重新出现

【钓鱼机制说明】
  1. 进入钓鱼界面后，右侧出现收杆圆盘
  2. 白色光珠在圆盘上持续循环移动
  3. 光珠经过蓝色区域时点击「拉一下」→ 水位线正常上涨
  4. 光珠经过黄色区域时点击「拉一下」→ 水位暴增（大幅上涨）
  5. 光珠不在有效区域时点击 = 失误，累计 3 次失误 → 钓鱼失败
  6. 水位线充满整个圆盘 → 钓鱼成功
  7. 圆盘消失 → 结果界面（领取/再来一次）

【目录结构】
  fishing_bot/
    main.py           ← 本文件（主脚本，含全部逻辑）
    config.json        ← 校准后的配置文件（自动生成）
    templates/        ← 弹窗模板图片目录（可选，增强弹窗检测）
    screenshots/      ← 运行时截图缓存目录（自动创建）
    requirements.txt   ← Python 依赖列表
    fishing_log.txt    ← 运行日志文件（自动生成）

【使用方法】
  1. 安装依赖：
     pip install opencv-python numpy
     或使用项目 venv：
     set PYTHONPATH=D:\\WorkBuddy-MemSpac\\.WorkBuddy\\binaries\\python\\envs\\default\\Lib\\site-packages
     python main.py test

  2. 雷电模拟器开启 ADB 调试，确认设备已连接：
     D:\\leidian\\LDPlayer9\\adb.exe devices

  3. 进入游戏 → 白雪镇 → 寒雪冰洞 → 钓鱼界面

  4. 首次运行：校准屏幕坐标
     python main.py calibrate

  5. 测试各模块是否正常
     python main.py test

  6. 开始自动钓鱼（支持失败后自动重试，支持自动再来一次）
     python main.py run

【配置说明】（config.json）
  "buttons.claim_x/y"    ← 「收杆/领取」按钮坐标（结果页）
  "buttons.retry_x/y"    ← 「再来一次」按钮坐标
  "retry.retry_on_failure" ← 是否失败后自动重试
  "retry.max_retries"      ← 最大重试次数（0=无限）
  "fishing.click_blue_probability" ← 蓝区点击概率（0~1）
  "detection.disc_lost_timeout"    ← 光珠消失多久判定结束（秒）
  "detection.bead_miss_threshold" ← 连续未检测到光珠多少次才判定结束（v3.1 新增）
================================================================================
"""

# ==================== 标准库导入 ====================
import os
import sys
import time
import json
import random
import math
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path

# ==================== 第三方库导入 ====================
import numpy as np
import cv2


# ============================================================
# 项目路径常量定义
# ============================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
TEMPLATE_DIR = SCRIPT_DIR / "templates"
SCREENSHOT_DIR = SCRIPT_DIR / "screenshots"
CONFIG_FILE = SCRIPT_DIR / "config.json"
LOG_FILE = SCRIPT_DIR / "fishing_log.txt"

TEMPLATE_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR.mkdir(exist_ok=True)


# ============================================================
# 日志配置
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("FishingBot")


# ============================================================
# ADB 可执行文件路径自动检测
# ============================================================
def _find_adb():
    """自动查找雷电模拟器或其他常见位置中的 adb.exe"""
    candidates = [
        r"D:\leidian\LDPlayer9\adb.exe",
        r"D:\Android\platform-tools\adb.exe",
        r"C:\Program Files\ldplayerbox\adb.exe",
        r"D:\ldplayerbox\adb.exe",
        r"D:\dnplayer2\adb.exe",
        r"C:\leidian\LDPlayer9\adb.exe",
        r"C:\Changzhi\dnplayer2\adb.exe",
    ]
    path_adb = shutil.which("adb")
    if path_adb:
        return path_adb
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"


def _detect_device():
    """自动检测第一个已连接的 ADB 设备，返回设备序列号或 None"""
    adb = _find_adb()
    result = subprocess.run(
        [adb, "devices"], capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split("\n")[1:]:
        line = line.strip()
        if line and "\tdevice" in line:
            return line.split("\t")[0]
    return None


ADB_PATH = _find_adb()


# ============================================================
# 配置文件读写函数
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


# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG = {
    "adb": {
        "device": "emulator-5554",
        "path": ADB_PATH,
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
        # 「拉一下」按钮（钓鱼界面）
        "reel_x": 1540,
        "reel_y": 825,
        # 「收杆/领取」按钮（结果页，v3.0 新增）
        "claim_x": 960,
        "claim_y": 750,
        # 「再来一次」按钮（结果页，v3.0 新增）
        "retry_x": 960,
        "retry_y": 850,
    },
    "detection": {
        "bead_brightness_min": 180,
        "bead_min_area": 15,
        "bead_max_area": 300,
        "match_threshold": 0.80,
        # ★ v3.0 新增：光珠消失多久判定为钓鱼结束（秒）
        "disc_lost_timeout": 4.0,
        # ★ v3.1 新增：连续多少次未检测到光珠才判定钓鱼结束
        "bead_miss_threshold": 8,
        # ★ v3.0 新增：结果页加载等待时间（秒）
        "result_wait": 2.0,
        # ★ v3.0 新增：再来一次后等待钓鱼界面加载（秒）
        "restart_wait": 2.5,
    },
    "timing": {
        "screenshot_cooldown": 0.06,
        "min_click_interval": 0.20,
        "animation_wait": 0.3,
        "popup_wait": 0.8,
        "idle_timeout": 15.0,
        # ★ v3.2 新增：无响应超时（秒），超时自动退出并通知
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
}


# ============================================================
# ADB 工具类
# ============================================================
class ADB:
    """ADB 操作封装类，所有方法均为类方法"""

    _adb_path = None

    @classmethod
    def get_adb(cls):
        """获取 adb.exe 路径（带缓存）"""
        if cls._adb_path is None:
            cfg = load_config()
            cls._adb_path = cfg.get("adb", {}).get("path", "adb")
            log.info(f"ADB 路径: {cls._adb_path}")
        return cls._adb_path

    @classmethod
    def connect(cls, device="127.0.0.1:5555"):
        """
        连接指定 ADB 设备
        - 对于 emulator-XXXX 本地设备，自动检测是否已在线，已在线则跳过
        - 仅对 "IP:端口" 格式执行 connect
        返回：bool，连接成功为 True
        """
        adb = cls.get_adb()
        # 先检查设备是否已在线
        result = subprocess.run(
            [adb, "devices"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.strip().split("\n")[1:]:
            line = line.strip()
            if line and "\tdevice" in line:
                online_device = line.split("\t")[0]
                if online_device == device:
                    log.info(f"ADB 设备已在线: {device}")
                    return True
        # 不在线，尝试 connect
        if ":" in device and not device.startswith("emulator"):
            result = subprocess.run(
                [adb, "connect", device],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout.strip()
            log.info(f"ADB 连接: {output}")
            return "connected" in output.lower() or "already" in output.lower()
        else:
            log.error(f"ADB 设备未在线且无法自动连接: {device}")
            return False

    @classmethod
    def screenshot(cls, save_path=None):
        """
        截图并返回 BGR 格式 numpy 数组
        使用唯一文件名避免写入冲突
        """
        adb = cls.get_adb()
        # 唯一文件名：时间戳 + 随机数
        fname = f"screen_{int(time.time() * 1000)}_{random.randint(0, 9999)}.png"
        remote_path = f"/sdcard/{fname}"
        local_tmp = SCREENSHOT_DIR / fname
        # 步骤1: 截图到模拟器
        subprocess.run([adb, "shell", "screencap", "-p", remote_path],
                      capture_output=True, timeout=10)
        # 步骤2: 延时确保写入完成
        time.sleep(0.05)
        # 步骤3: 拉取到本地
        subprocess.run([adb, "pull", remote_path, str(local_tmp)],
                      capture_output=True, timeout=10)
        # 步骤4: 清理远程文件
        subprocess.run([adb, "shell", "rm", "-f", remote_path],
                      capture_output=True, timeout=5)
        if local_tmp.exists():
            img = cv2.imread(str(local_tmp))
            if img is None:
                log.error("截图数据解码失败")
                return None
            if save_path:
                cv2.imwrite(str(save_path), img)
            # 删除临时文件
            if not save_path or str(local_tmp) != str(save_path):
                try:
                    local_tmp.unlink()
                except Exception:
                    pass
            return img
        log.error("截图文件未生成")
        return None

    @classmethod
    def tap(cls, x, y):
        """点击指定坐标（含 ±3 像素随机偏移）"""
        adb = cls.get_adb()
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        subprocess.run(
            [adb, "shell", "input", "tap",
             str(int(x) + offset_x), str(int(y) + offset_y)],
            capture_output=True, timeout=5
        )

    @classmethod
    def swipe(cls, x1, y1, x2, y2, duration=300):
        """滑动操作（预留接口）"""
        adb = cls.get_adb()
        subprocess.run(
            [adb, "shell", "input", "swipe",
             str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(duration)],
            capture_output=True, timeout=5
        )

    @classmethod
    def get_screen_size(cls):
        """获取模拟器屏幕分辨率，返回 (width, height) 或 None"""
        adb = cls.get_adb()
        result = subprocess.run(
            [adb, "shell", "wm", "size"],
            capture_output=True, text=True, timeout=5
        )
        line = result.stdout.strip()
        if ":" in line:
            size_str = line.split(":")[-1].strip()
            w, h = size_str.split("x")
            return int(w), int(h)
        return None


# ============================================================
# 图像识别类
# ============================================================
class Vision:
    """
    视觉识别模块：光珠定位、区域判定、弹窗匹配、Disc 可见性检测
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.disc = cfg["disc"]
        self.zones = cfg["zones"]
        self.det = cfg["detection"]

    def find_bead_on_disc(self, img):
        """
        【核心函数】在截图中定位光珠的位置（v3.1 增强版）
        策略：
          1. 灰度阈值（光珠灰度 ~237，比其他UI元素亮得多）
          2. 紧贴轨道的环形掩码（仅检测光珠运动环带）
          3. 圆形度校验（过滤不规则UI碎片）
          4. 轨道距离校验（距离中心必须是 bead_radius ± tolerance）
          5. 多维度候选打分（综合亮度、圆形度、轨道贴合度）
        注意：光珠非纯白色（BGR=174,242,250），偏暖色调，所以用灰度而非RGB等值检测
        返回：(angle, found)，angle 单位度 [0, 360)
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
        mask = np.zeros((h, w), dtype=np.uint8)
        inner_r = max(1, bead_r - track_tol)
        outer_r_mask = bead_r + track_tol
        cv2.circle(mask, (cx, cy), outer_r_mask, 255, -1)
        cv2.circle(mask, (cx, cy), inner_r, 0, -1)

        # ---- Step 2: 灰度亮度阈值 ----
        # 光珠灰度 ~237，背景 ~80-160，阈值设200即可有效分离
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

            # 轨道距离校验：光珠必须在 bead_radius 附近
            track_err = abs(dist - bead_r)
            if track_err > track_tol:
                continue

            # 圆形度校验：越接近圆（1.0），越可能是光珠
            perimeter = cv2.arcLength(cnt, True)
            if perimeter <= 0:
                continue
            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
            if circularity < circ_min:
                continue

            # 综合打分：圆形度 * 轨道贴合度 * 面积权重
            track_score = 1.0 - (track_err / track_tol)
            score = circularity * track_score * math.log1p(area)

            if score > best_score:
                best_score = score
                best_candidate = (bx, by, area, circularity, track_err)

        if best_candidate is not None:
            bx, by, area, circ, terr = best_candidate
            dx, dy = bx - cx, by - cy
            rad = math.atan2(dx, -dy)
            if rad < 0:
                rad += 2 * math.pi
            deg = math.degrees(rad)
            return deg, True
        return 0.0, False

    def which_zone(self, angle):
        """
        根据光珠角度判断所在区域
        返回："yellow"（黄区）、"blue"（蓝区）、"none"（无效区域）
        """
        ys, ye = self.zones["yellow_start"], self.zones["yellow_end"]
        bs, be = self.zones["blue_start"], self.zones["blue_end"]

        def in_range(a, s, e):
            """角度范围判断，支持跨 0° 环绕"""
            if s <= e:
                return s <= a <= e
            else:
                return a >= s or a <= e

        if in_range(angle, ys, ye):
            return "yellow"
        if in_range(angle, bs, be):
            return "blue"
        return "none"

    def is_disc_visible(self, img):
        """
        ★ v3.0 新增：检测圆盘是否仍可见
        方法：采样圆盘中心周围区域的颜色分布，判断是否与钓鱼界面一致
        返回：True（圆盘可见）/ False（圆盘消失，可能在结果页）
        """
        cx, cy = self.disc["center_x"], self.disc["center_y"]
        outer_r = self.disc["outer_radius"]
        h, w = img.shape[:2]

        # 确保采样区域不越界
        x1 = max(0, cx - outer_r)
        x2 = min(w, cx + outer_r)
        y1 = max(0, cy - outer_r)
        y2 = min(h, cy + outer_r)

        if x2 <= x1 or y2 <= y1:
            return False

        # 采样圆盘区域的图像
        disc_region = img[y1:y2, x1:x2]
        if disc_region.size == 0:
            return False

        # 计算圆盘区域的平均亮度和颜色方差
        gray = cv2.cvtColor(disc_region, cv2.COLOR_BGR2GRAY)
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)

        # 启发式判断：
        # - 钓鱼界面中圆盘通常有明亮的蓝/黄色区域，平均亮度 > 100，方差较大
        # - 结果页通常颜色单一，方差较小
        # - 若平均亮度 < 80 或方差 < 20，判定圆盘不可见
        if mean_brightness < 60 or std_brightness < 15:
            return False
        return True

    def match_template(self, img, template_name):
        """
        模板匹配：在截图中搜索指定模板图片
        返回：(x, y, confidence) 或 None
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

    def detect_popup(self, img):
        """
        检测屏幕上是否出现已知弹窗（依赖模板匹配）
        返回：dict 或 None
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


# ============================================================
# 钓鱼状态机（核心控制逻辑 v3.0）
# ============================================================
class FishingStateMachine:
    """
    钓鱼流程的状态机控制器

    状态流转（v3.0 更新）：
      IDLE → FISHING → ROUND_OVER → FISHING（循环）
      或 IDLE → FISHING → ROUND_OVER → STOP（达到上限）

    关键状态说明：
      - IDLE:       空闲，等待检测到光珠（即已进入钓鱼界面）
      - FISHING:    钓鱼中，检测光珠 → 点击「拉一下」→ 水位上涨
      - ROUND_OVER: 一轮结束，光珠消失 → 点击收杆/领取 → 点击再来一次
      - STOP:       停止，达到最大轮次或用户中断
    """

    STATE_IDLE = "idle"
    STATE_FISHING = "fishing"
    STATE_ROUND_OVER = "round_over"
    STATE_STOP = "stop"

    def __init__(self, cfg):
        """初始化状态机"""
        self.cfg = cfg
        self.state = self.STATE_IDLE
        self.round_count = 0                # 当前已完成钓鱼轮次计数
        self.retry_count = 0                # 连续失败重试次数
        self.last_bead_angle = None         # 上一帧光珠角度
        self.last_click_time = time.time()  # 上次点击时间戳
        self.last_bead_time = None          # ★ v3.0：最后一次检测到光珠的时间
        self.fishing_start_time = None      # 本轮钓鱼开始时间
        self.vision = Vision(cfg)           # 视觉识别模块
        self.miss_count = 0                 # 本轮失误计数
        self.click_count_this_round = 0     # ★ v3.0：本轮点击次数统计
        self.bead_miss_count = 0            # ★ v3.1：连续未检测到光珠的次数（用于确认钓鱼结束）
        # ★ v3.2：活动时间跟踪（用于无响应超时）
        self.last_activity_time = time.time()
        self.activity_timeout = 60.0         # 60秒无响应则退出

    def run(self):
        """
        【主循环】状态机入口函数
        持续运行直到达到最大轮次或用户中断（Ctrl+C）
        """
        log.info("=" * 50)
        log.info("钓鱼脚本启动 v3.1 (修复死循环)")
        log.info(f"优先黄区: {self.cfg['fishing']['prefer_yellow']}")
        log.info(f"蓝区点击率: {self.cfg['fishing']['click_blue_probability']}")
        log.info(f"光珠消失超时: {self.cfg['detection']['disc_lost_timeout']}秒")
        retry_cfg = self.cfg.get("retry", {})
        log.info(f"失败重试: {retry_cfg.get('retry_on_failure', True)}")
        log.info(f"最大重试: {retry_cfg.get('max_retries', 0)} (0=无限)")
        log.info(f"无响应超时: {self.activity_timeout:.0f}秒（超时自动退出并通知）")
        log.info("=" * 50)

        self.state = self.STATE_IDLE
        try:
            while self.state != self.STATE_STOP:
                # ★ v3.2：每次循环检查是否超时
                self._check_timeout()
                if self.state == self.STATE_STOP:
                    break

                if self.state == self.STATE_IDLE:
                    self._on_idle()
                elif self.state == self.STATE_FISHING:
                    self._on_fishing()
                elif self.state == self.STATE_ROUND_OVER:
                    self._on_round_over()
                else:
                    log.error(f"未知状态: {self.state}")
                    break
        except KeyboardInterrupt:
            log.info("用户中断（Ctrl+C），脚本停止")
        finally:
            log.info(f"脚本结束，共完成 {self.round_count} 轮钓鱼")

    # ================================================================
    # IDLE 状态：等待进入钓鱼界面
    # ================================================================
    def _on_idle(self):
        """
        空闲状态处理：
          - 截图检测光珠是否可见（确认已在钓鱼界面）
          - 若检测到光珠 → 切换到 FISHING
          - 若未检测到 → 提示用户手动操作
        """
        log.info("[状态] 空闲中，等待进入钓鱼界面...")
        while self.state == self.STATE_IDLE:
            img = ADB.screenshot()
            if img is None:
                time.sleep(1)
                continue

            # 检测弹窗（可能已有弹窗需要关闭）
            popup = self.vision.detect_popup(img)
            if popup:
                self._handle_popup(popup)
                time.sleep(self.cfg["timing"]["popup_wait"])
                continue

            # 尝试检测光珠
            angle, found = self.vision.find_bead_on_disc(img)
            if found:
                log.info("[状态] [OK] 检测到光珠，已进入钓鱼界面")
                self.state = self.STATE_FISHING
                self.fishing_start_time = time.time()
                self.last_bead_time = time.time()  # ★ 初始化光珠最后可见时间
                self.click_count_this_round = 0    # ★ 重置点击计数
                self.miss_count = 0
                self.bead_miss_count = 0           # ★ v3.1：重置连续未检测计数
                self._touch_activity()               # ★ v3.2：更新活动时间
                return
            else:
                log.info("  未在钓鱼界面，请手动进入 白雪镇 → 寒雪冰洞 → 钓鱼界面")
                time.sleep(3)

    # ================================================================
    # FISHING 状态：钓鱼进行中（核心逻辑）
    # ================================================================
    def _on_fishing(self):
        """
        【核心】钓鱼进行中状态处理：
          1. 截图 + 光珠检测
          2. 如果检测到光珠 → 判断区域 → 决策是否点击
          3. 如果未检测到光珠 → 累加消失时间 → 超时则判定钓鱼结束
          4. 弹窗检测（如果 templates/ 有模板图）
        """
        img = ADB.screenshot()
        if img is None:
            time.sleep(0.5)
            return

        # ---- 优先：弹窗检测 ----
        popup = self.vision.detect_popup(img)
        if popup:
            self._handle_popup(popup)
            return

        # ---- 光珠检测 ----
        angle, found = self.vision.find_bead_on_disc(img)
        now = time.time()

        if found:
            # ★ v3.1：检测到光珠，重置消失计时器和连续未检测计数器
            if self.last_bead_time is None:
                self.last_bead_time = now
            self.last_bead_time = now
            self.bead_miss_count = 0
            self._touch_activity()               # ★ v3.2：更新活动时间

            zone = self.vision.which_zone(angle)

            # ---- 点击决策 ----
            should_click = False
            reason = ""

            if zone == "yellow":
                # 黄区：高收益，必定点击
                should_click = True
                reason = "黄区-水位暴增"
            elif zone == "blue":
                # 蓝区：按概率点击
                prob = self.cfg["fishing"]["click_blue_probability"]
                if random.random() < prob:
                    should_click = True
                    reason = "蓝区-正常收杆"
                else:
                    reason = "蓝区-跳过"
            # zone == "none" → 不点击

            # ---- 执行点击 ----
            if should_click and (now - self.last_click_time) >= self.cfg["timing"]["min_click_interval"]:
                jitter = random.uniform(0.05, 0.20)
                time.sleep(jitter)

                reel_x = self.cfg["buttons"]["reel_x"]
                reel_y = self.cfg["buttons"]["reel_y"]
                ADB.tap(reel_x, reel_y)
                self.last_click_time = time.time()
                self.click_count_this_round += 1
                log.info(f"点击 #{self.click_count_this_round} | 区域={zone} | "
                         f"角度={angle:.0f}° | {reason}")

                # 点击后等待动画
                time.sleep(self.cfg["timing"]["animation_wait"])

            elif should_click:
                log.debug(f"点击间隔太短，跳过 | 区域={zone}")

            # 更新上一帧角度
            self.last_bead_angle = angle

        else:
            # ★ v3.1：未检测到光珠，累加连续未检测计数
            if self.last_bead_time is None:
                self.last_bead_time = now

            self.bead_miss_count += 1
            disc_lost_duration = now - self.last_bead_time
            disc_lost_timeout = self.cfg["detection"]["disc_lost_timeout"]
            bead_miss_threshold = self.cfg["detection"].get("bead_miss_threshold", 8)

            if disc_lost_duration > disc_lost_timeout and self.bead_miss_count >= bead_miss_threshold:
                # 同时满足超时 + 连续N次未检测到 → 判定钓鱼结束
                log.info("=" * 40)
                log.info(f"★ 光珠已消失 {disc_lost_duration:.1f}秒 "
                         f"(连续 {self.bead_miss_count} 次未检测到)，判定本轮钓鱼结束")
                log.info(f"  本轮点击次数: {self.click_count_this_round}")
                log.info("=" * 40)
                self.state = self.STATE_ROUND_OVER
                self.bead_miss_count = 0
                self.last_bead_time = None
                return
            elif self.bead_miss_count > 0 and self.bead_miss_count % 12 == 0:
                log.debug(f"未检测到光珠 (连续 {self.bead_miss_count} 次, "
                          f"已消失 {disc_lost_duration:.1f}s / {disc_lost_timeout}s)")

        # 超时检测：若距离上次点击太久，可能是异常
        if (now - self.last_click_time) > self.cfg["timing"]["idle_timeout"]:
            log.warning("空闲超时警告，可能检测失败，继续尝试...")

        # 截图间隔
        time.sleep(self.cfg["timing"]["screenshot_cooldown"])

    # ================================================================
    # ROUND_OVER 状态：处理钓鱼结束，点击收杆 + 再来一次
    # ================================================================
    def _on_round_over(self):
        """
        ★ v3.0 核心新增：一轮钓鱼结束后的处理流程

        流程：
          1. 等待结果界面加载完成
          2. 截图验证 disc 是否真的消失了（兜底确认）
          3. 点击「收杆/领取」按钮（如果有）
          4. 等待短暂动画
          5. 点击「再来一次」按钮
          6. 等待钓鱼界面重新加载
          7. 检测 disc 是否重新出现（确认已回到钓鱼界面）
          8. 若成功回到钓鱼界面 → 计数 +1，切换到 FISHING
          9. 若多次尝试失败 → 告警并进入 IDLE
        """
        log.info("[状态] 处理钓鱼结果...")
        result_wait = self.cfg["detection"]["result_wait"]
        restart_wait = self.cfg["detection"]["restart_wait"]

        # ---- 步骤1：等待结果界面完全加载 ----
        log.info(f"  (1/5) 等待结果界面加载 ({result_wait}秒)...")
        time.sleep(result_wait)

        # ---- 步骤2：确认 bead 已消失（用 bead 检测，不用 disc 可见性）----
        log.info("  (2/5) 确认 bead 已消失...")
        img = ADB.screenshot()
        if img is not None:
            angle, found = self.vision.find_bead_on_disc(img)
            if found:
                # bead 还能检测到 → 钓鱼还没结束，切回 FISHING
                log.warning(f"  ⚠ bead 仍可检测到 (角度={angle:.0f}°)，切回 FISHING")
                self.state = self.STATE_FISHING
                self.last_bead_time = time.time()
                self.bead_miss_count = 0
                return
        log.info("  [OK] bead 已消失，确认进入结果界面")

        # ---- 步骤3：点击「收杆/领取」按钮 ----
        claim_x = self.cfg["buttons"]["claim_x"]
        claim_y = self.cfg["buttons"]["claim_y"]
        log.info(f"  (3/5) 点击「收杆/领取」({claim_x}, {claim_y})...")
        ADB.tap(claim_x, claim_y)
        time.sleep(1.0)

        # ---- 步骤4：点击「再来一次」按钮 ----
        retry_x = self.cfg["buttons"]["retry_x"]
        retry_y = self.cfg["buttons"]["retry_y"]
        log.info(f"  (4/5) 点击「再来一次」({retry_x}, {retry_y})...")

        # 可能需要等待「再来一次」按钮出现（如果先有领取动画）
        time.sleep(0.5)
        ADB.tap(retry_x, retry_y)

        # ---- 步骤5：等待钓鱼界面重新加载 ----
        log.info(f"  (5/5) 等待钓鱼界面重新加载 ({restart_wait}秒)...")
        time.sleep(restart_wait)

        # ---- 验证：disc 是否重新出现 ----
        # 尝试多次检测（给游戏足够时间加载）
        max_disc_check_retries = 10
        disc_reappeared = False
        for check_i in range(max_disc_check_retries):
            img = ADB.screenshot()
            if img is not None:
                # 方式1：直接尝试检测光珠
                angle, found = self.vision.find_bead_on_disc(img)
                if found:
                    disc_reappeared = True
                    log.info(f"  [OK] disc 已重新出现（第 {check_i + 1} 次检测到光珠，角度={angle:.0f}°）")
                    break
            time.sleep(0.5)

        if disc_reappeared:
            # 成功回到钓鱼界面
            self.round_count += 1
            log.info(f"  [OK] 第 {self.round_count} 轮完成！开始新一轮钓鱼")
            self.state = self.STATE_FISHING
            self.last_bead_time = time.time()
            self.last_click_time = time.time()
            self.click_count_this_round = 0
            self.miss_count = 0
            self.bead_miss_count = 0           # ★ v3.1：重置连续未检测计数
        else:
            # 未能检测到 disc，可能「再来一次」按钮坐标不对
            log.warning("  ⚠ 未能检测到 disc 重新出现，尝试再次点击「再来一次」...")
            # 再试一次
            ADB.tap(retry_x, retry_y)
            time.sleep(restart_wait)

            # 再次检测
            for check_i in range(max_disc_check_retries):
                img = ADB.screenshot()
                if img is not None:
                    angle, found = self.vision.find_bead_on_disc(img)
                    if found:
                        disc_reappeared = True
                        log.info(f"  [OK] 第二次尝试成功！disc 已重新出现")
                        break
                time.sleep(0.5)

            if disc_reappeared:
                self.round_count += 1
                log.info(f"  [OK] 第 {self.round_count} 轮完成！开始新一轮钓鱼")
                self.state = self.STATE_FISHING
                self.last_bead_time = time.time()
                self.last_click_time = time.time()
                self.click_count_this_round = 0
                self.miss_count = 0
                self.bead_miss_count = 0           # ★ v3.1：重置连续未检测计数
            else:
                log.error("  [FAIL] 无法回到钓鱼界面！可能需要手动干预")
                log.error("    请检查「再来一次」按钮坐标是否正确")
                log.error(f"    当前坐标: ({retry_x}, {retry_y})")
                self.retry_count += 1
                retry_cfg = self.cfg.get("retry", {})
                if retry_cfg.get("retry_on_failure", True):
                    max_retries = retry_cfg.get("max_retries", 10)
                    if max_retries > 0 and self.retry_count > max_retries:
                        log.error(f"已达到最大重试次数 ({max_retries})，停止")
                        self.state = self.STATE_STOP
                    else:
                        log.info(f"重试 ({self.retry_count}/{max_retries})...")
                        self.state = self.STATE_IDLE
                else:
                    self.state = self.STATE_STOP

        # 检查是否达到最大轮次
        if self.round_count >= self.cfg["fishing"]["max_rounds"]:
            log.info(f"已达到最大钓鱼轮次 ({self.cfg['fishing']['max_rounds']})，停止")
            self.state = self.STATE_STOP

    # ================================================================
    # 弹窗处理（模板匹配）
    # ================================================================
    def _handle_popup(self, popup):
        """
        处理弹窗点击（依赖 templates/ 目录中的模板图）
        参数：popup: dict，包含类型和坐标
        """
        ptype = popup["type"]
        x, y = popup["x"], popup["y"]

        if ptype == "success":
            log.info("  [OK] 模板匹配：钓鱼成功！")
            self.round_count += 1
            self.retry_count = 0
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            if self.round_count >= self.cfg["fishing"]["max_rounds"]:
                log.info("已达到最大轮次，停止")
                self.state = self.STATE_STOP
            else:
                self.state = self.STATE_IDLE

        elif ptype == "failure":
            log.warning("  [FAIL] 模板匹配：钓鱼失败")
            self.retry_count += 1
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            retry_cfg = self.cfg.get("retry", {})
            if retry_cfg.get("retry_on_failure", True):
                max_retries = retry_cfg.get("max_retries", 10)
                if max_retries > 0 and self.retry_count > max_retries:
                    log.error(f"达到最大重试次数 ({max_retries})，停止")
                    self.state = self.STATE_STOP
                else:
                    log.info(f"失败后重试 ({self.retry_count}/{max_retries})...")
                    time.sleep(retry_cfg.get("retry_delay", 2.0))
                    self.state = self.STATE_IDLE
            else:
                self.state = self.STATE_STOP

        elif ptype == "start_fishing":
            log.info("  点击「开始钓鱼」...")
            ADB.tap(x, y)
            time.sleep(2.0)
            self.state = self.STATE_FISHING
            self.last_bead_time = time.time()

        else:
            # 通用弹窗（关闭按钮等）
            log.info(f"  关闭弹窗: {ptype}")
            ADB.tap(x, y)
            time.sleep(self.cfg["timing"]["popup_wait"])
            self.state = self.STATE_IDLE

    # ================================================================
    # ★ v3.2 新增：活动时间跟踪 + 超时退出 + 通知
    # ================================================================
    def _touch_activity(self):
        """更新最后活动时间戳（有实质响应时调用）"""
        self.last_activity_time = time.time()

    def _check_timeout(self):
        """
        检查是否超过 activity_timeout 秒无响应
        检查两个已有时间戳：last_click_time 和 last_bead_time
        超时则报错、写 alert 文件、通知用户、退出
        """
        now = time.time()
        no_click = (now - self.last_click_time) > self.activity_timeout
        no_bead = self.last_bead_time is None or (now - self.last_bead_time) > self.activity_timeout
        if no_click and no_bead:
            msg = f"[超时退出] 已 {self.activity_timeout:.0f} 秒无任何点击或检测到光珠，脚本自动退出！"
            log.error("=" * 50)
            log.error(msg)
            log.error(f"  最后点击: {time.strftime('%H:%M:%S', time.localtime(self.last_click_time))}")
            if self.last_bead_time:
                log.error(f"  最后光珠: {time.strftime('%H:%M:%S', time.localtime(self.last_bead_time))}")
            log.error("=" * 50)
            self._alert(msg)
            self.state = self.STATE_STOP

    def _alert(self, msg):
        """
        发送通知给用户
        方式1：写 alert.txt 文件（始终执行）
        方式2：Windows 弹窗通知（仅 Windows 可用）
        """
        # 方式1：写 alert 文件
        alert_file = SCRIPT_DIR / "alert.txt"
        try:
            with open(alert_file, "w", encoding="utf-8") as f:
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"消息: {msg}\n")
            log.info(f"  已写通知文件: {alert_file}")
        except Exception as e:
            log.warning(f"  写 alert 文件失败: {e}")

        # 方式2：Windows Toast 通知（仅 Windows）
        try:
            import ctypes
            # 使用 Windows API 弹MessageBox
            ctypes.windll.user32.MessageBoxW(
                0,
                f"钓鱼脚本超时退出！\n\n{msg}\n\n请检查游戏状态。",
                "钓鱼脚本通知",
                0x40 | 0x1  # ICON_INFORMATION | MB_OKCANCEL
            )
        except Exception:
            pass  # 非 Windows 或失败则忽略

    def _on_retry(self):
        """
        ★ v3.2 新增：「再来一次」模式入口
        假设当前屏幕已显示结果页（有「再来一次」按钮）
        直接点击「再来一次」→ 等待钓鱼界面加载 → 进入 FISHING
        """
        log.info("=" * 50)
        log.info("[模式] 「再来一次」模式：直接从结果页开始")
        log.info("=" * 50)

        retry_x = self.cfg["buttons"]["retry_x"]
        retry_y = self.cfg["buttons"]["retry_y"]
        claim_x = self.cfg["buttons"]["claim_x"]
        claim_y = self.cfg["buttons"]["claim_y"]
        restart_wait = self.cfg["detection"]["restart_wait"]

        # 步骤1：先尝试点击「收杆/领取」（如果结果页还在）
        log.info(f"  (1/4) 尝试点击「收杆/领取」({claim_x}, {claim_y})...")
        ADB.tap(claim_x, claim_y)
        self._touch_activity()
        time.sleep(1.0)

        # 步骤2：点击「再来一次」
        log.info(f"  (2/4) 点击「再来一次」({retry_x}, {retry_y})...")
        ADB.tap(retry_x, retry_y)
        self._touch_activity()
        time.sleep(restart_wait)

        # 步骤3：等待钓鱼界面加载（检测光珠出现）
        log.info(f"  (3/4) 等待钓鱼界面加载（最多 {restart_wait * 3:.0f} 秒）...")
        max_wait = int(restart_wait * 3)
        for i in range(max_wait * 2):  # 每 0.5s 检测一次
            img = ADB.screenshot()
            if img is not None:
                angle, found = self.vision.find_bead_on_disc(img)
                if found:
                    log.info(f"  [OK] 检测到光珠（角度={angle:.0f}°），进入钓鱼")
                    self._touch_activity()
                    self.state = self.STATE_FISHING
                    self.fishing_start_time = time.time()
                    self.last_bead_time = time.time()
                    self.last_click_time = time.time()
                    self.click_count_this_round = 0
                    self.miss_count = 0
                    self.bead_miss_count = 0
                    return
            time.sleep(0.5)
            if (i + 1) % 4 == 0:
                log.debug(f"  仍在等待钓鱼界面加载... ({ (i+1)//2 }s)")

        # 步骤4：超时，报错
        log.error("  [FAIL] 点击「再来一次」后未检测到钓鱼界面！")
        log.error(f"    请手动确认「再来一次」按钮坐标是否正确: ({retry_x}, {retry_y})")
        self._alert("「再来一次」模式失败：未检测到钓鱼界面，请检查按钮坐标！")
        self.state = self.STATE_STOP


# ============================================================
# 主函数入口
# ============================================================
def main():
    """解析命令行参数，分发到对应功能"""
    import argparse
    parser = argparse.ArgumentParser(description="江南百景图 白雪镇 钓鱼自动化脚本 v3.2")
    parser.add_argument("action", choices=["run", "retry", "test", "calibrate", "help"],
                       help="run=自动钓鱼, retry=从再来一次开始, test=测试模式, calibrate=校准坐标, help=帮助")
    args = parser.parse_args()

    if args.action == "run":
        cfg = load_config()
        fsm = FishingStateMachine(cfg)
        fsm.run()
    elif args.action == "retry":
        retry_mode()
    elif args.action == "test":
        test_mode()
    elif args.action == "calibrate":
        calibrate_mode()
    elif args.action == "help":
        print(__doc__)



# ============================================================
# ★ v3.2 新增：「再来一次」模式入口
# ============================================================
def retry_mode():
    """
    从结果页「再来一次」按钮开始执行脚本
    假设当前屏幕已显示结果页（有「再来一次」按钮）
    """
    log.info('=' * 50)
    log.info('[模式] 「再来一次」模式启动')
    log.info('=' * 50)

    cfg = load_config()
    fsm = FishingStateMachine(cfg)
    fsm._on_retry()  # 点击「再来一次」，等待钓鱼界面
    fsm.run()          # 进入主循环


def test_mode():
    """
    测试模式：逐步验证各模块功能
    ADB 连接 → 截图 → 光珠检测 → Disc 可见性 → 坐标验证
    """
    cfg = load_config()
    print("=" * 50)
    print(" 钓鱼脚本 v3.0 测试模式")
    print("=" * 50)

    # [1/5] ADB 连接
    print("\n[1/5] ADB 连接...")
    device = _detect_device()
    if device:
        print(f"  [OK] 检测到设备: {device}")
        cfg["adb"]["device"] = device
    else:
        print("  [FAIL] 未检测到 ADB 设备")
        return
    print("  [OK] ADB 就绪")

    # [2/5] 截图测试
    print("\n[2/5] 截图测试...")
    img = ADB.screenshot(SCREENSHOT_DIR / "test.png")
    if img is None:
        print("  [FAIL] 截图失败")
        return
    h, w = img.shape[:2]
    print(f"  [OK] 截图成功, 分辨率={w}x{h}")
    if cfg["screen"]["width"] != w or cfg["screen"]["height"] != h:
        log.info(f"分辨率已更新为 {w}x{h}，更新配置")
        cfg["screen"]["width"] = w
        cfg["screen"]["height"] = h
        save_config(cfg)

    # [3/5] 光珠检测
    print("\n[3/5] 光珠检测...")
    vision = Vision(cfg)
    angle, found = vision.find_bead_on_disc(img)
    if found:
        zone = vision.which_zone(angle)
        print(f"  [OK] 检测到光珠, 角度={angle:.1f}度, 区域={zone}")
    else:
        print("  [FAIL] 未检测到光珠")
        print(f"    屏幕: {w}x{h}")
        print("    提示: 可能当前不在钓鱼界面")
        print("    请进入钓鱼界面后重新测试")
        return

    # [4/5] Disc 可见性检测
    print("\n[4/5] Disc 可见性检测...")
    disc_ok = vision.is_disc_visible(img)
    if disc_ok:
        print("  [OK] disc 可见（确认在钓鱼界面）")
    else:
        print("  [WARN] disc 不可见（可能在结果页？）")

    # [5/5] 坐标验证
    print("\n[5/5] 按钮坐标验证...")
    btns = cfg["buttons"]
    print(f"  「拉一下」:    ({btns['reel_x']}, {btns['reel_y']})")
    print(f"  「收杆/领取」:  ({btns['claim_x']}, {btns['claim_y']})")
    print(f"  「再来一次」:  ({btns['retry_x']}, {btns['retry_y']})")
    print(f"  当前分辨率: {cfg['screen']['width']}x{cfg['screen']['height']}")
    print("\n  测试完成！坐标不正确请运行: python main.py calibrate")
    print("  确认无误请运行: python main.py run")


def calibrate_mode():
    """
    校准模式：交互式引导用户标注关键坐标
    适用于首次运行或切换分辨率后
    """
    print("=" * 60)
    print(" 校准模式 v3.0（交互式坐标标注）")
    print("=" * 60)
    print("请在游戏中进入钓鱼界面，使用截图工具")
    print("（如微信截图 Alt+A、QQ 截图 Ctrl+Alt+A）")
    print("将鼠标悬停在以下位置，记录坐标值：\n")

    cfg = load_config()

    try:
        # [1/5] 圆盘中心
        print("【1/5】收杆圆盘中心坐标")
        print("  将鼠标悬停在圆盘的正中心")
        cx = int(input("  圆盘中心 X: "))
        cy = int(input("  圆盘中心 Y: "))
        cfg["disc"]["center_x"] = cx
        cfg["disc"]["center_y"] = cy

        # [2/5] 「拉一下」按钮
        print("\n【2/5】「拉一下」按钮（钓鱼界面中的红色按钮）")
        bx = int(input("  「拉一下」按钮 X: "))
        by = int(input("  「拉一下」按钮 Y: "))
        cfg["buttons"]["reel_x"] = bx
        cfg["buttons"]["reel_y"] = by

        # [3/5] 「收杆/领取」按钮（结果页）
        print("\n【3/5】「收杆/领取」按钮（结果页，钓鱼结束后的弹窗）")
        print("  提示：如果在结果页看不到「收杆」按钮，直接回车跳过")
        cx_input = input("  「收杆/领取」按钮 X [跳过]: ")
        if cx_input.strip():
            cy_input = input("  「收杆/领取」按钮 Y: ")
            cfg["buttons"]["claim_x"] = int(cx_input)
            cfg["buttons"]["claim_y"] = int(cy_input)

        # [4/5] 「再来一次」按钮（结果页）
        print("\n【4/5】「再来一次」按钮（结果页，收杆之后出现）")
        rx_input = input("  「再来一次」按钮 X: ")
        if rx_input.strip():
            ry_input = input("  「再来一次」按钮 Y: ")
            cfg["buttons"]["retry_x"] = int(rx_input)
            cfg["buttons"]["retry_y"] = int(ry_input)

        # [5/5] 区域角度
        print("\n【5/5】蓝/黄区域角度（一般使用默认值即可，直接回车跳过）")
        print("  默认: 蓝区 0°~300°, 黄区 300°~360°")
        ys = input("  黄区起始角度 [300]: ")
        ye = input("  黄区结束角度 [360]: ")
        if ys.strip():
            cfg["zones"]["yellow_start"] = int(ys)
        if ye.strip():
            cfg["zones"]["yellow_end"] = int(ye)

        save_config(cfg)
        print("\n[OK] 校准完成！配置已保存到 config.json")
        print("  请运行 python main.py test 验证校准效果")

    except KeyboardInterrupt:
        print("\n校准已取消")
    except Exception as e:
        log.error(f"校准失败: {e}")


if __name__ == "__main__":
    main()
