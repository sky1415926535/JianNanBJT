#!/usr/bin/env python3
"""
定位大地图入口按钮 - 全面检测左侧UI区域所有按钮
"""
import cv2
import numpy as np
import sys, os, time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config

cfg = load_config()
screenshot_path = 'screenshots/bigmap_find.png'

# 1. 先截图
print('[1/5] 截图当前游戏界面...')
ADB.screenshot(save_path=screenshot_path)
print(f'  截图保存到: {screenshot_path}')

img = cv2.imread(screenshot_path)
if img is None:
    print('ERROR: 无法读取截图')
    sys.exit(1)

h, w = img.shape[:2]
print(f'  图片尺寸: {w}x{h}')

# 2. 分析整个左侧UI区域 (x: 0-200)
left_region = img[:, 0:200]
gray = cv2.cvtColor(left_region, cv2.COLOR_BGR2GRAY)

# 边缘检测
edges = cv2.Canny(gray, 50, 150)

# 查找轮廓
contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'\n[2/5] 左侧区域找到 {len(contours)} 个轮廓')

# 3. 筛选有意义的按钮轮廓
buttons = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 200:  # 过滤太小
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    # 过滤太扁或太窄
    if bw < 10 or bh < 10:
        continue
    if bw > 180 or bh > 180:  # 过滤太大（可能是背景区域）
        continue
    
    cx = x_c + bw // 2
    cy = y_c + bh // 2
    
    # 计算圆形度
    perimeter = cv2.arcLength(c, True)
    circularity = 0
    if perimeter > 0:
        circularity = 4 * np.pi * area / (perimeter * perimeter)
    
    buttons.append({
        'cx': cx, 'cy': cy,
        'x': x_c, 'y': y_c, 'w': bw, 'h': bh,
        'area': area,
        'circularity': circularity
    })

# 按y坐标排序
buttons.sort(key=lambda b: b['cy'])

print(f'\n[3/5] 有效按钮 ({len(buttons)} 个):')
print(f'  {"ID":<4} {"X":<6} {"Y":<6} {"W":<5} {"H":<5} {"面积":<8} {"圆形度":<8}')
print(f'  {"-"*50}')
for i, b in enumerate(buttons):
    circ_str = f"{b['circularity']:.3f}" if b['circularity'] > 0 else "N/A"
    print(f'  {i:<4} {b["cx"]:<6} {b["cy"]:<6} {b["w"]:<5} {b["h"]:<5} {b["area"]:<8.0f} {circ_str:<8}')

# 4. 在左侧区域标注所有按钮
debug_img = left_region.copy()
for i, b in enumerate(buttons):
    color = (0, 255, 0)
    # 圆形的用红色标注
    if b['circularity'] > 0.6:
        color = (0, 0, 255)
        cv2.circle(debug_img, (b['cx'], b['cy']), max(b['w'], b['h'])//2, color, 2)
        cv2.putText(debug_img, f"C{i} area={int(b['area'])}", (b['x'], b['y']-5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
    else:
        cv2.rectangle(debug_img, (b['x'], b['y']), (b['x']+b['w'], b['y']+b['h']), color, 1)
        cv2.putText(debug_img, f"B{i}", (b['x'], b['y']-5),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)

cv2.imwrite('screenshots/bigmap_debug_left.png', debug_img)
print(f'\n[4/5] 调试图片保存到: screenshots/bigmap_debug_left.png')

# 5. 特别关注底部区域 - 寻找"州府印"圆形图章
print(f'\n[5/5] 底部圆形按钮分析 (y > 800):')
bottom_circular = [b for b in buttons if b['cy'] > 800 and b['circularity'] > 0.4]
print(f'  找到 {len(bottom_circular)} 个圆形按钮')
for b in bottom_circular:
    print(f'  坐标: ({b["cx"]}, {b["cy"]})  圆形度: {b["circularity"]:.3f}  面积: {b["area"]:.0f}')

# 也检查一下 y=500-800 区间的轮廓（可能是地图入口图标）
print(f'\n中间区域按钮分析 (y 500-800):')
mid_buttons = [b for b in buttons if 500 <= b['cy'] <= 800]
for b in mid_buttons:
    tag = "圆形" if b['circularity'] > 0.5 else "矩形"
    print(f'  {tag} 坐标: ({b["cx"]}, {b["cy"]})  {b["w"]}x{b["h"]}  圆形度: {b["circularity"]:.3f}')

# 6. 检查右上角和整个屏幕，看看有没有其他地图入口线索
# 保存全图标注版本
full_debug = img.copy()
for b in buttons:
    bx, by = b['x'], b['y']  # 这些是left_region的坐标，相对于全图就是x+0
    color = (0, 255, 0)
    if b['circularity'] > 0.6:
        color = (0, 0, 255)
    cv2.rectangle(full_debug, (bx, by), (bx+b['w'], by+b['h']), color, 1)

cv2.imwrite('screenshots/bigmap_debug_full.png', full_debug)
print(f'\n全图调试保存到: screenshots/bigmap_debug_full.png')
print('Done!')
