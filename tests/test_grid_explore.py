#!/usr/bin/env python3
"""
网格化系统探索 - 点击屏幕各处找出所有可交互元素
"""
import cv2
import numpy as np
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH
from common.config import save_config

def adb_back():
    subprocess.run([ADB_PATH, "shell", "input", "keyevent", "4"],
                  capture_output=True, timeout=5)

# 网格点击（重要区域）
# 5x3 网格覆盖全屏
grid = []
for y in range(180, 960, 180):
    for x in range(160, 1800, 320):
        grid.append((x, y, f'网格({x},{y})'))

print(f'网格探索: {len(grid)} 个点')
print('=' * 60)

# 先确保在游戏内（点击中心几次）
for _ in range(3):
    ADB.tap(960, 500)
    time.sleep(0.3)

# 基准截图
baseline = 'screenshots/grid_baseline.png'
ADB.screenshot(save_path=baseline)
b_img = cv2.imread(baseline)

for i, (x, y, desc) in enumerate(grid):
    print(f'\n[{i+1}/{len(grid)}] ({x},{y}) - {desc}')
    ADB.tap(x, y)
    time.sleep(2.5)
    
    after = f'screenshots/grid_{i+1}.png'
    ADB.screenshot(save_path=after)
    
    a_img = cv2.imread(after)
    if a_img is None:
        continue
    
    diff = cv2.absdiff(b_img, a_img)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    change = np.sum(diff_gray > 30) / diff_gray.size
    
    if change > 0.01:
        print(f'  ★ 变化率: {change*100:.1f}% - 此坐标有响应!')
        
        # 分析新画面
        gray = cv2.cvtColor(a_img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(a_img, cv2.COLOR_BGR2HSV)
        green_pct = np.sum((hsv[:,:,0] >= 35) & (hsv[:,:,0] <= 85)) / hsv[:,:,0].size * 100
        
        # 检查是否是大地图
        center = a_img[200:880, 400:1520]
        avg = np.mean(center, axis=(0,1))
        
        print(f'    绿色调: {green_pct:.1f}%  中部色: B={avg[0]:.0f} G={avg[1]:.0f} R={avg[2]:.0f}')
        
        if green_pct > 5:
            print(f'    >>> 可能是大地图! <<<')
            cfg = load_config()
            cfg['prefecture']['big_map_enter_btn'] = {
                'x': x, 'y': y,
                'comment': f'大地图入口 (网格探索)'
            }
            save_config(cfg)
            break
        
        # 返回原界面
        adb_back()
        time.sleep(2)
        ADB.tap(960, 500)
        time.sleep(0.5)
        
        # 更新基准（可能回不到完全相同的状态）
        ADB.screenshot(save_path=baseline)
        b_img = cv2.imread(baseline)
    else:
        print(f'  - 无变化')

print('\nDone!')
