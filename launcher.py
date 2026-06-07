#!/usr/bin/env python
"""
============================================================================
 江南百景图 自动化脚本 — 统一入口（v4.0）
============================================================================
 环境：雷电模拟器9 + ADB + Python + OpenCV
 运行平台：Windows

【v4.1 更新说明】（OCR 文字识别完整实现）
  1. ★ 模块化架构：公共模块(common) + 功能模块(fishing/map_switch/travel_bag)
  2. ★ 统一入口 launcher.py：通过子命令切换不同功能
  3. ★ 大地图州府切换 OCR 完整实现（PaddleOCR / EasyOCR / MSER 三引擎）
  4. ★ common/ocr.py — OCR 工具模块（自动检测引擎、统一识别接口）
  5. ★ 多模式降级：OCR → 坐标 → 模板，自动按序尝试
  6.  行囊城镇切换骨架（travel_bag/town_switch.py — 待截图实现）

【模块依赖】
  - common/adb.py        → ADB 操作封装
  - common/config.py     → 配置加载/保存
  - common/paths.py      → 路径常量
  - common/vision.py     → 视觉识别（光珠/模板/红色按钮/MSER）
  - common/ocr.py        → OCR 文字识别（PaddleOCR/EasyOCR/MSER 三引擎）
  - fishing/bot.py       → 钓鱼状态机
  - map_switch/prefecture.py   → 州府切换（OCR/坐标/模板 三模式降级）
  - travel_bag/town_switch.py → 城镇切换（骨架）

【使用方法】
  python launcher.py fish                 # 启动钓鱼脚本
  python launcher.py fish --retry         # 从"再来一次"开始钓鱼
  python launcher.py switch-prefecture    # 切换州府（OCR 文字识别优先）
  python launcher.py switch-prefecture --target 苏州府  # 指定目标
  python launcher.py diagnose-map         # 截图+OCR诊断（推荐首次运行）
  python launcher.py switch-town          # 切换城镇（骨架）
  python launcher.py test                 # 测试各模块
  python launcher.py calibrate            # 交互式坐标校准
  python launcher.py menu                 # 交互式菜单（默认）
============================================================================
"""
import os
import sys
import time
import logging

# ---- 确保项目根目录在 sys.path 中 ----
# 这样无论用户从哪个目录运行，都能正确 import common / fishing 等模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# ============================================================
# 日志配置
# ============================================================
# 日志同时输出到：
#   1. 控制台（stdout）—— 实时查看
#   2. 文件（fishing_log.txt）—— 持久化记录
LOG_FILE = os.path.join(SCRIPT_DIR, "fishing_log.txt")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("Launcher")


# ============================================================
# 功能分发函数
# ============================================================
def run_fishing(retry_mode=False):
    """
    启动钓鱼脚本（主入口函数）。

    执行流程：
      1. 加载配置（load_config）
      2. 自动检测 ADB 设备（detect_device）
      3. 连接设备（ADB.connect）
      4. 创建 FishingBot 实例
      5. 根据 retry_mode 调用：
         - retry_mode=True  → bot.start_from_retry()
         - retry_mode=False → bot.run()

    参数：
      retry_mode: bool，是否从结果页「再来一次」按钮开始

    副作用：
      - 可能修改 config.json 中的 adb.device 字段
      - 写 fishing_log.txt（通过 logging 模块）
      - 控制游戏画面（ADB.tap 点击操作）

    异常：
      - ADB 设备未检测到 → 打印错误日志，直接返回
      - ADB 连接失败 → 打印错误日志，直接返回
    """
    from common import ADB, detect_device, load_config
    from fishing import FishingBot

    cfg = load_config()

    # ADB 设备检测
    device = detect_device()
    if device:
        log.info(f"检测到 ADB 设备: {device}")
        cfg["adb"]["device"] = device
    else:
        log.error("未检测到 ADB 设备！请确认雷电模拟器已启动并开启 ADB 调试")
        return

    if not ADB.connect(cfg["adb"]["device"]):
        log.error("ADB 连接失败！")
        return

    bot = FishingBot(cfg)
    if retry_mode:
        bot.start_from_retry()
    bot.run()


def switch_prefecture(target=None):
    """
    切换州府（v4.0 完整实现）。

    支持三种定位模式（按配置 mode 字段选择）:
      - coordinate: 坐标直点（最快，需预配置 map_coord）
      - template:   模板匹配 + 滑动搜索（需州府截图模板）
      - mser:       MSER 文字检测（需 OCR 库，预留）

    执行流程：
      1. 连接 ADB
      2. 进入大地图（点击大地图按钮）
      3. 截图 → 定位目标州府 → 点击
      4. 处理确认弹窗
      5. 等待城镇加载完成

    参数：
      target: str | None，目标州府名称
             若未提供，使用 config.json 中 prefecture.target 的值

    返回：
      None（结果通过日志输出）
    """
    from common import ADB, detect_device, load_config
    from map_switch import PrefectureSwitcher

    cfg = load_config()
    device = detect_device()
    if not device:
        log.error("未检测到 ADB 设备！")
        return
    cfg["adb"]["device"] = device
    if not ADB.connect(device):
        log.error("ADB 连接失败！")
        return

    switcher = PrefectureSwitcher(cfg)
    switcher.switch_to(target)


def switch_town(target=None):
    """
    切换行囊中的城镇（v4.0 骨架功能）。

    当前状态：骨架代码，等待用户提供行囊界面截图后实现具体逻辑。

    执行流程（未来）：
      1. 连接 ADB
      2. 打开行囊界面（模拟器点击）
      3. 滚动城镇列表
      4. 匹配目标城镇名称
      5. 点击进入目标城镇

    参数：
      target: str | None，目标城镇名称
             若未提供，使用 config.json 中 travel_bag.target 的值

    返回：
      None（结果通过日志输出）
    """
    from common import ADB, detect_device, load_config
    from travel_bag import TownSwitcher

    cfg = load_config()
    device = detect_device()
    if not device:
        log.error("未检测到 ADB 设备！")
        return
    cfg["adb"]["device"] = device
    if not ADB.connect(device):
        log.error("ADB 连接失败！")
        return

    switcher = TownSwitcher(cfg)
    switcher.switch_to(target)


def run_diagnose_map():
    """
    州府坐标诊断模式。

    截取当前屏幕并保存到 screenshots/ 目录，
    用户用图片查看器打开截图后获取州府坐标，
    填入 config.json → prefecture.prefectures.<name>.map_coord。

    执行流程：
      1. 连接 ADB
      2. 截图保存为 screenshots/big_map_diagnose.png
      3. 输出日志引导用户获取坐标

    返回：
      None
    """
    from common import ADB, detect_device, load_config
    from map_switch import run_diagnose

    cfg = load_config()
    device = detect_device()
    if not device:
        log.error("未检测到 ADB 设备！")
        return
    cfg["adb"]["device"] = device
    if not ADB.connect(device):
        log.error("ADB 连接失败！")
        return

    run_diagnose()


def run_test():
    """
    测试模式：逐步验证各模块功能。

    测试步骤：
      [1/5] ADB 连接测试
      [2/5] 截图测试（同时自动校准分辨率）
      [3/5] 光珠检测测试
      [4/5] Disc 可见性检测测试
      [5/5] 按钮坐标验证

    用途：
      - 首次运行前验证环境
      - 修改坐标/配置后回归测试
      - 排查脚本异常

    注意：
      测试 [3/5] 时光珠可能检测不到（脚本运行时游戏需处于钓鱼界面）。
    """
    from common import ADB, Vision, detect_device, load_config, save_config, SCREENSHOT_DIR
    cfg = load_config()
    print("=" * 50)
    print(" 江南百景图 自动化脚本 v4.0 测试模式")
    print("=" * 50)

    # [1/5] ADB 连接
    print("\n[1/5] ADB 连接...")
    device = detect_device()
    if device:
        print(f"  [OK] 检测到设备: {device}")
        cfg["adb"]["device"] = device
    else:
        print("  [FAIL] 未检测到 ADB 设备")
        return
    if not ADB.connect(device):
        print("  [FAIL] ADB 连接失败")
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
        log.info(f"分辨率已更新为 {w}x{h}")
        cfg["screen"]["width"] = w
        cfg["screen"]["height"] = h
        save_config(cfg)

    # [3/5] 光珠检测
    print("\n[3/5] 光珠检测...")
    vision = Vision(cfg)
    angle, found = vision.find_bead_on_disc(img)
    if found:
        zone = vision.which_zone(angle)
        print(f"  [OK] 检测到光珠, 角度={angle:.1f}deg, 区域={zone}")
    else:
        print("  [FAIL] 未检测到光珠（当前可能不在钓鱼界面）")

    # [4/5] Disc 可见性
    print("\n[4/5] Disc 可见性检测...")
    disc_ok = vision.is_disc_visible(img)
    if disc_ok:
        print("  [OK] disc 可见")
    else:
        print("  [WARN] disc 不可见")

    # [5/5] 按钮坐标
    print("\n[5/5] 按钮坐标验证...")
    btns = cfg["buttons"]
    print(f"  「拉一下」:     ({btns['reel_x']}, {btns['reel_y']})")
    print(f"  「收杆/领取」:  ({btns['claim_x']}, {btns['claim_y']})")
    print(f"  「再来一次」:   ({btns['retry_x']}, {btns['retry_y']})")
    print(f"  当前分辨率: {cfg['screen']['width']}x{cfg['screen']['height']}")
    print("\n  测试完成！坐标不正确请运行: python launcher.py calibrate")
    print("  确认无误请运行: python launcher.py fish")


def run_calibrate():
    """
    校准模式：交互式引导用户标注关键坐标。

    校准项目（共 5 项）：
      [1/5] 收杆圆盘中心坐标（最重要！）
      [2/5] 「拉一下」按钮坐标
      [3/5] 「收杆/领取」按钮坐标（可选）
      [4/5] 「再来一次」按钮坐标
      [5/5] 蓝/黄区域角度（直接回车使用默认）

    使用方法：
      1. 将游戏停留在钓鱼界面
      2. 使用截图工具（微信 Alt+A / QQ Ctrl+Alt+A）
      3. 鼠标悬停在目标位置，从截图工具中读取坐标
      4. 按提示输入坐标值

    注意：
      坐标值因模拟器分辨率不同而变化，
      1920×1080 的默认值已适配雷电模拟器9 默认分辨率。
    """
    from common import load_config, save_config

    print("=" * 60)
    print(" 校准模式 v4.0（交互式坐标标注）")
    print("=" * 60)
    print("请在游戏中进入钓鱼界面，使用截图工具")
    print("（如微信截图 Alt+A、QQ 截图 Ctrl+Alt+A）")
    print("将鼠标悬停在以下位置，记录坐标值：\n")

    cfg = load_config()

    try:
        print("【1/5】收杆圆盘中心坐标")
        cx = int(input("  圆盘中心 X: "))
        cy = int(input("  圆盘中心 Y: "))
        cfg["disc"]["center_x"] = cx
        cfg["disc"]["center_y"] = cy

        print("\n【2/5】「拉一下」按钮（红色按钮）")
        bx = int(input("  X: "))
        by = int(input("  Y: "))
        cfg["buttons"]["reel_x"] = bx
        cfg["buttons"]["reel_y"] = by

        print("\n【3/5】「收杆/领取」按钮（结果页）")
        cx_in = input("  X [跳过]: ")
        if cx_in.strip():
            cy_in = input("  Y: ")
            cfg["buttons"]["claim_x"] = int(cx_in)
            cfg["buttons"]["claim_y"] = int(cy_in)

        print("\n【4/5】「再来一次」按钮（结果页）")
        rx_in = input("  X: ")
        if rx_in.strip():
            ry_in = input("  Y: ")
            cfg["buttons"]["retry_x"] = int(rx_in)
            cfg["buttons"]["retry_y"] = int(ry_in)

        print("\n【5/5】蓝/黄区域角度（直接回车使用默认）")
        print("  默认: 蓝区 0deg~300deg, 黄区 300deg~360deg")
        ys = input("  黄区起始角度 [300]: ")
        ye = input("  黄区结束角度 [360]: ")
        if ys.strip():
            cfg["zones"]["yellow_start"] = int(ys)
        if ye.strip():
            cfg["zones"]["yellow_end"] = int(ye)

        save_config(cfg)
        print("\n[OK] 校准完成！请运行 python launcher.py test 验证")

    except KeyboardInterrupt:
        print("\n校准已取消")
    except Exception as e:
        log.error(f"校准失败: {e}")


def run_menu():
    """
    交互式菜单：引导用户选择要执行的功能。

    菜单选项：
      [1] 启动钓鱼
      [2] 从「再来一次」开始钓鱼
      [3] 切换州府
      [4] 切换行囊城镇（骨架）
      [5] 州府坐标诊断
      [6] 测试模式
      [7] 坐标校准
      [0] 退出

    注意：
      菜单模式不会传递 --target 参数给 switch-prefecture / switch-town，
      若需指定目标，请使用命令行模式。
    """
    print("=" * 50)
    print(" 江南百景图 自动化脚本 v4.0")
    print("=" * 50)
    print("  [1] 启动钓鱼")
    print("  [2] 从「再来一次」开始钓鱼")
    print("  [3] 切换州府")
    print("  [4] 切换行囊城镇（骨架）")
    print("  [5] 州府坐标诊断")
    print("  [6] 测试模式")
    print("  [7] 坐标校准")
    print("  [0] 退出")
    print("-" * 50)
    choice = input(" 请选择 [1]: ").strip()
    if not choice:
        choice = "1"
    actions = {
        "1": lambda: run_fishing(),
        "2": lambda: run_fishing(retry_mode=True),
        "3": switch_prefecture,
        "4": switch_town,
        "5": run_diagnose_map,
        "6": run_test,
        "7": run_calibrate,
    }
    if choice in actions:
        actions[choice]()
    elif choice == "0":
        print("已退出")


# ============================================================
# 命令行入口（argparse）
# ============================================================
def main():
    """
    命令行入口函数：解析参数并分发到对应功能函数。

    子命令：
      fish            → run_fishing(retry_mode=False)
      fish --retry   → run_fishing(retry_mode=True)
      switch-prefecture [--target X] → switch_prefecture(target=X)
      switch-town [--target X]       → switch_town(target=X)
      test            → run_test()
      calibrate       → run_calibrate()
      menu（默认）    → run_menu()

    若未提供子命令，默认启动交互式菜单（menu）。
    """
    import argparse
    parser = argparse.ArgumentParser(
        description="江南百景图 自动化脚本 v4.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  python launcher.py fish                 # 启动钓鱼
  python launcher.py fish --retry         # 从再来一次开始钓鱼
  python launcher.py switch-prefecture    # 切换州府
  python launcher.py switch-prefecture --target 白雪镇  # 指定目标
  python launcher.py diagnose-map         # 州府坐标诊断
  python launcher.py switch-town          # 切换城镇
  python launcher.py test                 # 测试模式
  python launcher.py calibrate            # 坐标校准
  python launcher.py menu                 # 交互菜单
        """
    )
    parser.add_argument(
        "action",
        choices=["fish", "switch-prefecture", "switch-town", "diagnose-map", "test", "calibrate", "menu"],
        nargs="?",
        default="menu",
        help="fish=钓鱼, switch-prefecture=切换州府, switch-town=切换城镇, "
             "diagnose-map=州府坐标诊断, test=测试, calibrate=校准, menu=菜单"
    )
    parser.add_argument(
        "--retry", action="store_true",
        help="从「再来一次」开始（仅 fish 模式下有效）"
    )
    parser.add_argument(
        "--target", type=str, default=None,
        help="目标州府/城镇名称（switch-prefecture / switch-town 模式下有效）"
    )
    args = parser.parse_args()

    if args.action == "fish":
        run_fishing(retry_mode=args.retry)
    elif args.action == "switch-prefecture":
        switch_prefecture(target=args.target)
    elif args.action == "switch-town":
        switch_town(target=args.target)
    elif args.action == "diagnose-map":
        run_diagnose_map()
    elif args.action == "test":
        run_test()
    elif args.action == "calibrate":
        run_calibrate()
    elif args.action == "menu":
        run_menu()


if __name__ == "__main__":
    main()
