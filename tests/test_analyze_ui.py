#!/usr/bin/env python3
"""
重新分析游戏UI - 不按返回键，直接分析当前界面
"""
import cv2
import numpy as np
import sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB

ss_path = 'screenshots/analyze_ui.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR')
    sys.exit(1)

h, w = img.shape[:2]
print(f'尺寸: {w}x{h}')

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ======= 按行分析亮度分布 ========
print('\n======= 水平扫描 (每行平均灰度) =======')
for y in range(0, h, 30):
    row = gray[y:min(y+30, h), :]
    avg = np.mean(row)
    min_v = np.min(row)
    max_v = np.max(row)
    bar = '#' * min(int(avg/2), 80)
    marker = ''
    if avg < 60:
        marker = ' ★暗色'
    elif avg > 200:
        marker = ' ☆亮色'
    print(f'  y={y:>4}-{min(y+30, h):>4}: avg={avg:5.0f} min={min_v:3.0f} max={max_v:3.0f} {bar}{marker}')

# ======= 按列分析亮度分布 ========
print('\n======= 垂直扫描 (每列平均灰度) =======')
for x in range(0, w, 40):
    col = gray[:, x:min(x+40, w)]
    avg = np.mean(col)
    min_v = np.min(col)
    max_v = np.max(col)
    marker = ''
    if avg < 60:
        marker = ' ★暗色'
    print(f'  x={x:>4}-{min(x+40, w):>4}: avg={avg:5.0f} min={min_v:3.0f} max={max_v:3.0f}{marker}')

# ======= 网格颜色分析 ========
print('\n======= 网格颜色分析 (B,G,R) =======')
for gy in range(0, h, h//6):
    for gx in range(0, w, w//6):
        cell = img[gy:min(gy+h//6, h), gx:min(gx+w//6, w)]
        avg = np.mean(cell, axis=(0,1))
        print(f'  [{gx:>4},{gy:>4}]: B={avg[0]:3.0f} G={avg[1]:3.0f} R={avg[2]:3.0f}')
