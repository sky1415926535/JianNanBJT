#!/usr/bin/env python3
"""
验证是否真的进入大地图 - 多维度分析
"""
import cv2
import numpy as np
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH

def adb_back():
    subprocess.run(
        [ADB_PATH, "shell", "input", "keyevent", "4"],
        capture_output=True, timeout=5
    )

# 先确保停在城镇视图
adb_back()
time.sleep(1.5)

# 关闭弹窗
print('关闭弹窗...')
ADB.tap(960, 500)
time.sleep(0.3)
ADB.tap(1800, 100)
time.sleep(0.3)
ADB.tap(960, 400)
time.sleep(0.3)

# 截图城镇视图
print('截图城镇视图...')
town = ADB.screenshot(save_path='screenshots/verify_town.png')

# 点击 (52, 1028)
print('点击 (52, 1028)...')
ADB.tap(52, 1028)
time.sleep(3.0)

# 截图大地图
print('截图大地图...')
bigmap = ADB.screenshot(save_path='screenshots/verify_bigmap.png')

if bigmap is None:
    print('ERROR: 截图失败')
    sys.exit(1)

h, w = bigmap.shape[:2]
print(f'图片尺寸: {w}x{h}')

# ========== 分析1: 颜色分布 ==========
print('\n========== 颜色分布分析 ==========')

# 把图分成 6x4 网格，分析每格的颜色
grid_cols, grid_rows = 6, 4
cell_w, cell_h = w // grid_cols, h // grid_rows

print('网格颜色 (B, G, R) - 绿色通道 > 红色通道 = 大地图特征:')
map_like_cells = 0
for r in range(grid_rows):
    row_str = f'  行{r}: '
    for c in range(grid_cols):
        cell = bigmap[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
        avg = np.mean(cell, axis=(0, 1))
        g_gt_r = avg[1] > avg[2]  # G > R = 偏绿
        if g_gt_r:
            map_like_cells += 1
        marker = '✓' if g_gt_r else ' '
        row_str += f'[{marker}](B{avg[0]:.0f}G{avg[1]:.0f}R{avg[2]:.0f}) '
    print(row_str)

print(f'  偏绿格子: {map_like_cells}/{grid_cols*grid_rows}')

# ========== 分析2: 寻找"关闭"按钮 (大地图右上角常见) ==========
print('\n========== 寻找返回/关闭按钮 ==========')

# 检查右上角是否有浅色按钮 (x: 1800-1920, y: 0-100)
top_right = bigmap[0:100, 1750:1920]
tr_gray = cv2.cvtColor(top_right, cv2.COLOR_BGR2GRAY)
_, tr_bin = cv2.threshold(tr_gray, 200, 255, cv2.THRESH_BINARY)
tr_bright = np.sum(tr_bin > 0)
tr_total = tr_bin.size
tr_ratio = tr_bright / tr_total
print(f'  右上角亮色比例: {tr_ratio:.3f}')

# 检查左上角是否有返回箭头 (x: 0-100, y: 0-100)
top_left = bigmap[0:100, 0:100]
tl_gray = cv2.cvtColor(top_left, cv2.COLOR_BGR2GRAY)
_, tl_bin = cv2.threshold(tl_gray, 200, 255, cv2.THRESH_BINARY)
tl_bright = np.sum(tl_bin > 0)
tl_total = tl_bin.size
tl_ratio = tl_bright / tl_total
print(f'  左上角亮色比例: {tl_ratio:.3f}')

# ========== 分析3: 检查是否有大地图特有的UI元素 ==========
print('\n========== 大地图UI特征判断 ==========')

# 大地图特征：
# 1. 顶部通常有深色标题栏
# 2. 左上角有返回按钮
# 3. 整体色调偏绿/棕 (地图色调)
# 4. 没有左侧大面积的暗色竖栏（城镇视图有）

# 检查顶部标题栏
top_bar = bigmap[0:60, 0:w]
top_bar_gray = cv2.cvtColor(top_bar, cv2.COLOR_BGR2GRAY)
top_dark = np.sum(top_bar_gray < 50) / top_bar_gray.size
print(f'  顶部深色标题栏比例: {top_dark:.3f}')

# 检查左侧暗色竖栏
left_strip = bigmap[200:800, 0:80]
left_strip_gray = cv2.cvtColor(left_strip, cv2.COLOR_BGR2GRAY)
left_dark = np.sum(left_strip_gray < 40) / left_strip_gray.size
print(f'  左侧暗色竖栏比例: {left_dark:.3f} (城镇视图通常 > 0.3)')

# 整体颜色
total_avg = np.mean(bigmap, axis=(0, 1))
print(f'  全图平均色: B={total_avg[0]:.0f} G={total_avg[1]:.0f} R={total_avg[2]:.0f}')

# ========== 分析4: 与城镇视图对比 ==========
print('\n========== 城镇vs大地图 差异对比 ==========')
if town is not None:
    diff = cv2.absdiff(town, bigmap)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    significant_change = np.sum(diff_gray > 30) / diff_gray.size
    print(f'  显著变化像素比例: {significant_change:.3f} (越大 = 界面变化越大)')
    
    # 保存差异图
    cv2.imwrite('screenshots/verify_diff.png', diff)

# ========== 综合判断 ==========
print('\n========== 综合判断 ==========')
score = 0
# 偏绿格子多
if map_like_cells >= 8:
    print('  ✓ 偏绿区域多 (地图色调)')
    score += 1
# 左侧无暗色竖栏（不是城镇视图）
if left_dark < 0.2:
    print('  ✓ 左侧无大暗色竖栏 (非城镇视图)')
    score += 1
# 顶部有标题栏
if top_dark > 0.03:
    print('  ✓ 顶部有标题栏')
    score += 1
# 界面变化大
if significant_change > 0.3:
    print('  ✓ 界面发生了显著变化')
    score += 1
# 右上角有按钮
if tr_ratio > 0.1:
    print('  ✓ 右上角有UI元素')
    score += 1

if score >= 4:
    print(f'\n  >>> 确认: 已进入大地图界面! (得分: {score}/5)')
elif score >= 2:
    print(f'\n  >>> 疑似: 可能进入了大地图或其他界面 (得分: {score}/5)')
else:
    print(f'\n  >>> 未进入大地图 (得分: {score}/5)')

print('\n请查看 screenshots/verify_bigmap.png 人工确认')
