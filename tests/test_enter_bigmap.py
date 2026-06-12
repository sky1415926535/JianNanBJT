"""
测试：点击左下角州府印进入大地图
验证：大地图检测逻辑是否正确工作

用法: python test_enter_bigmap.py
"""

import sys
import time
import cv2
import numpy as np

sys.path.insert(0, '.')
from common import ADB, load_config

cfg = load_config()
enter_btn = cfg['prefecture']['big_map_enter_btn']
BTN_X = enter_btn['x']
BTN_Y = enter_btn['y']

print("=" * 50)
print(f"州府印坐标: ({BTN_X}, {BTN_Y})")
print("=" * 50)


def is_on_big_map(img):
    """
    检测当前是否在大地图界面。
    
    大地图特征：
    1. 左下角无大面积红色印章（州府印消失）
    2. 整体绿色/棕色调（地图颜色）
    3. 左下角出现了返回按钮（小按钮）
    """
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # --- 特征1: 左下角州府印检测 ---
    # 城镇视图：左下角 (0-250, 700-1080) 有大面积红色印章
    lb = img[700:1080, 0:250]
    lb_hsv = hsv[700:1080, 0:250]
    red1 = cv2.inRange(lb_hsv, np.array([0, 100, 80]), np.array([15, 255, 255]))
    red2 = cv2.inRange(lb_hsv, np.array([160, 100, 80]), np.array([180, 255, 255]))
    lb_red_pct = np.sum(cv2.bitwise_or(red1, red2) > 0) / lb_hsv[:, :, 0].size * 100

    # --- 特征2: 整体绿色调比例 ---
    # 大地图通常包含地图底图（绿色/棕色调）
    green_mask = cv2.inRange(hsv, np.array([35, 30, 50]), np.array([90, 255, 255]))
    green_pct = np.sum(green_mask > 0) / (h * w) * 100

    # --- 特征3: 屏幕整体色彩标准差 ---
    # 大地图画面比城镇视图更均匀（建筑物轮廓较少）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    std_val = np.std(gray)

    # --- 特征4: 中心区域颜色（大地图中央是地图底图）---
    center = img[200:880, 300:1620]
    center_avg = np.mean(center, axis=(0, 1))  # B, G, R
    # 大地图：G > R，棕绿色调；城镇：R > G（暖色调，建筑）
    center_green_dominant = center_avg[1] > center_avg[2]  # G > R

    print(f"\n[检测结果]")
    print(f"  左下角红色比例: {lb_red_pct:.1f}% (城镇视图通常>30%)")
    print(f"  整体绿色比例:   {green_pct:.1f}%")
    print(f"  灰度标准差:     {std_val:.1f}")
    print(f"  中心G>R(地图色): {center_green_dominant}")
    print(f"  中心平均色: B={center_avg[0]:.0f} G={center_avg[1]:.0f} R={center_avg[2]:.0f}")

    # 判断逻辑：
    # 城镇视图 → 左下角红色大印章明显（>25%）
    # 大地图   → 左下角红色消失（<10%），整体偏绿或偏棕
    if lb_red_pct < 10:
        print("  >>> 判断: 大地图 (左下角红色印章消失)")
        return True, lb_red_pct, green_pct, "big_map"
    elif lb_red_pct > 25:
        print("  >>> 判断: 城镇视图 (左下角有大红色印章)")
        return False, lb_red_pct, green_pct, "town"
    else:
        # 边界情况，看绿色比例
        if green_pct > 15 or center_green_dominant:
            print("  >>> 判断: 可能是大地图 (绿色调较多)")
            return True, lb_red_pct, green_pct, "maybe_big_map"
        else:
            print("  >>> 判断: 不确定，可能在过渡中")
            return False, lb_red_pct, green_pct, "unknown"


# ============================
# 主测试流程
# ============================

print("\n[步骤1] 截图当前状态...")
before_img = ADB.screenshot(save_path='screenshots/bigmap_before.png')
if before_img is None:
    print("ERROR: 截图失败！")
    sys.exit(1)

print("点击前状态分析:")
on_map_before, red_before, green_before, state_before = is_on_big_map(before_img)
print(f"当前状态: {state_before}")

if on_map_before:
    print("\n[提示] 当前已在大地图界面！")
    sys.exit(0)

print(f"\n[步骤2] 点击州府印 ({BTN_X}, {BTN_Y})...")
ADB.tap(BTN_X, BTN_Y)

print("[步骤3] 等待加载 (2.5秒)...")
time.sleep(2.5)

print("\n[步骤4] 截图并检测是否进入大地图...")
after_img = ADB.screenshot(save_path='screenshots/bigmap_after.png')
if after_img is None:
    print("ERROR: 截图失败！")
    sys.exit(1)

on_map_after, red_after, green_after, state_after = is_on_big_map(after_img)

# 计算变化率
diff = cv2.absdiff(before_img, after_img)
diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
change_pct = np.sum(diff_gray > 30) / diff_gray.size * 100

print(f"\n[结果汇总]")
print(f"  点击前: 红色={red_before:.1f}% 绿色={green_before:.1f}% 状态={state_before}")
print(f"  点击后: 红色={red_after:.1f}% 绿色={green_after:.1f}% 状态={state_after}")
print(f"  画面变化率: {change_pct:.1f}%")

print()
if on_map_after:
    print("✅ 成功进入大地图！")
    print(f"   → 州府印坐标 ({BTN_X}, {BTN_Y}) 有效")
else:
    print("❌ 未检测到大地图界面")
    print(f"   → 请检查截图 screenshots/bigmap_after.png")
    if change_pct < 1.0:
        print("   → 画面几乎无变化，可能点击未响应")
    elif change_pct > 30:
        print(f"   → 画面变化 {change_pct:.1f}%，进入了其他界面")
