#!/usr/bin/env python3
"""
逐个测试底部圆形按钮，找出大地图入口
先关闭弹窗，再依次测试坐标
"""
import cv2
import numpy as np
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH

def adb_back():
    """按返回键"""
    subprocess.run(
        [ADB_PATH, "shell", "input", "keyevent", "4"],
        capture_output=True, timeout=5
    )

def adb_home():
    """按Home键"""
    subprocess.run(
        [ADB_PATH, "shell", "input", "keyevent", "3"],
        capture_output=True, timeout=5
    )

def analyze_screen(screenshot_path, label=""):
    """分析截图特征"""
    img = cv2.imread(screenshot_path)
    if img is None:
        print(f'  [ERROR] 无法读取 {screenshot_path}')
        return {}
    h, w = img.shape[:2]
    
    # 顶部区域颜色
    top_strip = img[0:50, :]
    top_avg = np.mean(top_strip, axis=(0, 1))
    
    # 左下角暗色区域比例
    left_bottom = img[h-200:h, 0:200]
    dark_pixels = np.sum(np.all(left_bottom < 80, axis=2))
    dark_ratio = dark_pixels / (200 * 200)
    
    # 中部颜色
    center = img[h//3:2*h//3, w//3:2*w//3]
    center_avg = np.mean(center, axis=(0, 1))
    
    # 检查左侧是否有竖栏（城镇视图特征）
    left_full = img[0:h, 0:130]
    left_dark = np.sum(np.all(left_full < 60, axis=2)) / (left_full.shape[0] * left_full.shape[1])
    
    # 顶部深色条（可能是大地图标题栏）
    top_bar = img[0:80, 0:w]
    top_dark = np.sum(np.all(top_bar < 50, axis=2)) / (top_bar.shape[0] * top_bar.shape[1])
    
    result = {
        'dark_ratio_bl': dark_ratio,
        'left_dark': left_dark,
        'top_dark': top_dark,
        'top_avg': top_avg,
        'center_avg': center_avg,
        'b': center_avg[0], 'g': center_avg[1], 'r': center_avg[2],
    }
    
    if label:
        print(f'  [{label}]')
    print(f'  顶部暗条: {top_dark:.3f}  左侧暗栏: {left_dark:.3f}  左下暗角: {dark_ratio:.3f}')
    print(f'  顶部色: B={top_avg[0]:.0f} G={top_avg[1]:.0f} R={top_avg[2]:.0f}')
    print(f'  中部色: B={center_avg[0]:.0f} G={center_avg[1]:.0f} R={center_avg[2]:.0f}')
    
    return result

def is_big_map(result):
    """判断是否为大地图界面"""
    if not result:
        return False
    # 大地图特征:
    # 1. 左侧没有大面积暗色竖栏 (left_dark < 0.15)
    # 2. 顶部有暗色标题栏 (top_dark > 0.05)
    # 3. 中部偏绿 (g > r) - 地图是绿色调的
    # 4. 左下无暗角
    checks = [
        result['left_dark'] < 0.15,
        result['top_dark'] > 0.03,
        result['g'] > result['r'],
        result['dark_ratio_bl'] < 0.15,
    ]
    score = sum(1 for c in checks if c)
    return score >= 3

# 候选坐标
candidates = [
    (150, 1018, "底部偏右圆形(circ=0.833, area=520)"),
    (52, 1028, "底部偏左圆形(circ=0.817, area=946)"),
    (55, 969, "底部小圆形(circ=0.551)"),
    (68, 528, "中部大圆形(area=10119)"),
]

def dismiss_popups():
    """关闭可能的弹窗"""
    print('  关闭弹窗...')
    ADB.tap(960, 500)
    time.sleep(0.4)
    ADB.tap(1800, 100)
    time.sleep(0.4)
    ADB.tap(960, 400)
    time.sleep(0.4)

print('=' * 60)
print('测试底部圆形按钮 - 寻找大地图入口')
print('=' * 60)

# 先关闭弹窗并拍基准
dismiss_popups()
time.sleep(1.0)

baseline = 'screenshots/test_baseline.png'
ADB.screenshot(save_path=baseline)
print(f'\n[基准截图分析]')
baseline_result = analyze_screen(baseline, "城镇视图基准")

for i, (x, y, desc) in enumerate(candidates):
    print(f'\n{"="*50}')
    print(f'测试[{i+1}/{len(candidates)}]: ({x}, {y}) - {desc}')
    print(f'{"="*50}')
    
    before = f'screenshots/test_{i+1}_before.png'
    ADB.screenshot(save_path=before)
    
    print(f'  点击 ({x}, {y})...')
    ADB.tap(x, y)
    time.sleep(3.0)
    
    after = f'screenshots/test_{i+1}_after.png'
    ADB.screenshot(save_path=after)
    result = analyze_screen(after, f"测试{i+1}-after")
    
    map_check = is_big_map(result)
    print(f'  >>> 大地图判断: {"进入大地图!" if map_check else "不是大地图"}')
    
    if map_check:
        print(f'\n  *** 找到大地图入口! 坐标: ({x}, {y}) ***')
        # 更新config
        cfg = load_config()
        cfg['prefecture']['big_map_enter_btn'] = {'x': x, 'y': y, 'comment': f'大地图入口坐标({desc})'}
        from common.config import save_config
        save_config(cfg)
        print(f'  config.json 已更新!')
        break
    
    # 返回城镇视图
    if not map_check and i < len(candidates) - 1:
        print(f'  按返回键...')
        adb_back()
        time.sleep(1.5)
        dismiss_popups()
        time.sleep(1.0)

print('\nDone!')
