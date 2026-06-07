"""
ADB 工具模块
~~~~~~~~~~~~~

封装所有 Android Debug Bridge 操作，供各功能模块调用。
支持自动查找雷电模拟器自带的 adb.exe，无需手动配置路径。

主要功能：
  - 自动检测 adb.exe 路径（多常见安装位置兜底）
  - 自动检测已连接的设备（emulator-XXXX 或 IP:端口）
  - 截图并拉取到本地（唯一文件名防并发冲突）
  - 点击操作（含随机偏移模拟人工操作）
  - 滑动操作（用于地图/列表滚动）
  - 屏幕分辨率获取
"""
import os
import sys
import time
import random
import subprocess
import shutil
import logging

from .paths import SCREENSHOT_DIR
from .config import load_config

log = logging.getLogger("Common.ADB")

# ============================================================
# ADB 可执行文件路径自动检测
# ============================================================
def find_adb():
    """自动查找雷电模拟器或其他常见位置中的 adb.exe"""
    candidates = [
        r"D:\\leidian\\LDPlayer9\\adb.exe",
        r"D:\\Android\\platform-tools\\adb.exe",
        r"C:\\Program Files\\ldplayerbox\\adb.exe",
        r"D:\\ldplayerbox\\adb.exe",
        r"D:\\dnplayer2\\adb.exe",
        r"C:\\leidian\\LDPlayer9\\adb.exe",
        r"C:\\Changzhi\\dnplayer2\\adb.exe",
    ]
    path_adb = shutil.which("adb")
    if path_adb:
        return path_adb
    for c in candidates:
        if os.path.exists(c):
            return c
    return "adb"


def detect_device():
    """自动检测第一个已连接的 ADB 设备，返回设备序列号或 None"""
    adb = find_adb()
    result = subprocess.run(
        [adb, "devices"], capture_output=True, text=True, timeout=5
    )
    for line in result.stdout.strip().split("\n")[1:]:
        line = line.strip()
        if line and "\tdevice" in line:
            return line.split("\t")[0]
    return None


# 启动时检测
ADB_PATH = find_adb()


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
        连接指定 ADB 设备。

        行为逻辑：
          1. 先执行 `adb devices` 检查目标设备是否已在线
             - 已在线：直接返回 True（无需重复 connect）
           - 未在线：继续下一步
          2. 设备串号含 ":" 且不是 "emulator" 开头 → 执行 `adb connect`
             - 返回值含 "connected" 或 "already" → 成功
          3. 本地 emulator 设备未在线 → 返回 False（需用户手动启动模拟器）

        参数：
          device: ADB 设备标识，格式为 "IP:端口" 或 "emulator-XXXX"

        返回：
          bool: 连接成功为 True
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
        截图并返回 BGR 格式 numpy 数组。

        执行流程（4 步）：
          1. `adb shell screencap -p /sdcard/{fname}` → 保存到模拟器
          2. `time.sleep(0.05)` → 等待写入完成
          3. `adb pull /sdcard/{fname} {local_tmp}` → 拉取到本地临时文件
          4. `adb shell rm -f /sdcard/{fname}` → 清理模拟器端文件

        参数：
          save_path: 可选，指定保存路径；若提供则额外保存一份到该路径

        返回：
          numpy.ndarray | None: BGR 格式图像数组，失败返回 None
        """
        import cv2

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
        """点击指定坐标（含 +-3 像素随机偏移）"""
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
        """滑动操作"""
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
