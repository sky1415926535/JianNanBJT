#!/usr/bin/env python3
"""
全面分析游戏屏幕布局，理解UI结构
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

# 确保在城镇视图
adb_back()
time.sleep(1.5)
ADB.tap(960, 500); time.sleep(0.3)
ADB.tap(1800, 100); time.sleep(0.3)
ADB.tap(960, 900); time.sleep(0.3)

ss_path = 'screenshots/full_analysis.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR')
    sys.exit(1)

h, w = img.shape[:2]
print(f'图片尺寸: {w}x{h}')

# ======= 1. 暗色区域分析 (找UI面板) ========
print('\n======= 1. 暗色区域分布 =======')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# 分析每一列的平均亮度
print('垂直暗色条(每一列平均亮度):')
col_brightness = []
for x in range(0, w, 20):
    strip = gray[0:h, x:min(x+20, w)]
    avg = np.mean(strip)
    col_brightness.append((x, avg))
    if avg < 80:
        print(f'  x={x:>4}-{min(x+20,w):>4}: {avg:5.1f} ★暗色')

# 分析水平暗色条
print('\n水平暗色条(每一行平均亮度):')
row_brightness = []
for y in range(0, h, 20):
    strip = gray[y:min(y+20,h), 0:w]
    avg = np.mean(strip)
    row_brightness.append((y, avg))
    if avg < 80:
        print(f'  y={y:>4}-{min(y+20,h):>4}: {avg:5.1f} ★暗色')

# ======= 2. 分段区域分析 ========
print('\n======= 2. 关键区域分析 ========')

# 左下角
regions = {
    '左上角(0-200,0-200)': img[0:200, 0:200],
    '右上角(1720-1920,0-150)': img[0:150, 1720:1920],
    '左下角(0-200,880-1080)': img[880:1080, 0:200],
    '右下角(1720-1920,930-1080)': img[930:1080, 1720:1920],
    '底部中间(500-1420,900-1080)': img[900:1080, 500:1420],
    '左侧竖列(0-150,200-800)': img[200:800, 0:150],
    '顶部栏(0-1920,0-100)': img[0:100, 0:1920],
}

for name, region in regions.items():
    avg = np.mean(region, axis=(0, 1))
    gray_avg = np.mean(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY))
    # 找该区域内的轮廓
    r_gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(r_gray, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    significant = [c for c in contours if cv2.contourArea(c) > 200]
    print(f'  {name}')
    print(f'    平均色: B={avg[0]:.0f} G={avg[1]:.0f} R={avg[2]:.0f}  灰度={gray_avg:.0f}  物体={len(significant)}个')

# ======= 3. 寻找文字区域 (高对比度) ========
print('\n======= 3. 寻找文字/标签区域 =======')
# 使用 MSER 或简单的高对比度检测
lap = cv2.Laplacian(gray, cv2.CV_64F)
lap_abs = np.abs(lap)

# 分析哪些区域有高对比度 (可能包含文字)
high_contrast = lap_abs > 30
print('高对比度区域分布:')
for y_start in range(0, h, 100):
    for x_start in range(0, w, 100):
        patch = high_contrast[y_start:min(y_start+100,h), x_start:min(x_start+100,w)]
        ratio = np.sum(patch) / patch.size
        if ratio > 0.05:
            print(f'  ({x_start:>4},{y_start:>4}) 对比度比例={ratio:.3f}')

# ======= 4. 检测按钮形状 ========
print('\n======= 4. 按钮形状检测 (全图) =======')

# 用更宽松的参数
edges_full = cv2.Canny(gray, 40, 120)
contours_full, _ = cv2.findContours(edges_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# 筛选矩形/方形按钮
buttons = []
for c in contours_full:
    area = cv2.contourArea(c)
    if area < 500 or area > 50000:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    if bw < 15 or bh < 15:
        continue
    
    # 矩形度
    rect_area = bw * bh
    rect_ratio = area / rect_area if rect_area > 0 else 0
    
    # 宽高比
    aspect = bw / bh if bh > 0 else 0
    
    # 圆形度
    perimeter = cv2.arcLength(c, True)
    circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
    
    cx, cy = x_c + bw//2, y_c + bh//2
    
    # 分类
    if circularity > 0.7:
        btype = '圆形'
    elif 0.3 < aspect < 3.0 and rect_ratio > 0.5:
        btype = '矩形'
    else:
        btype = '其他'
    
    buttons.append({
        'type': btype, 'cx': cx, 'cy': cy,
        'x': x_c, 'y': y_c, 'w': bw, 'h': bh,
        'area': area, 'aspect': aspect, 'circ': circularity
    })

# 按区域分组
print(f'找到 {len(buttons)} 个按钮形状')
print('\n底部栏按钮 (y>900):')
for b in buttons:
    if b['cy'] > 900:
        print(f'  [{b["type"]:>4}] ({b["cx"]:>4},{b["cy"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.2f}')

print('\n左侧按钮 (x<200, y<850):')
for b in buttons:
    if b['cx'] < 200 and b['cy'] < 850:
        print(f'  [{b["type"]:>4}] ({b["cx"]:>4},{b["cy"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.2f}')

print('\n有圆形潜力的按钮 (circ>0.5, area>800):')
for b in buttons:
    if b['circ'] > 0.5 and b['area'] > 800:
        print(f'  [{b["type"]:>4}] ({b["cx"]:>4},{b["cy"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.3f}')

# ======= 5. 颜色分块 - 理解布局 ========
print('\n======= 5. 颜色聚类分析 =======')
# 把图像缩小后做颜色聚类
small = cv2.resize(img, (64, 36))
pixels = small.reshape(-1, 3).astype(np.float32)

# 简单统计不同色调的分布
hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
hue = hsv[:,:,0].flatten()
sat = hsv[:,:,1].flatten()

# 绿色调像素 (H: 35-80)
green_hue = np.sum((hue >= 35) & (hue <= 80))
# 蓝色调像素 (H: 90-130)
blue_hue = np.sum((hue >= 90) & (hue <= 130))
# 红色调像素 (H: 0-15 or 160-180)
red_hue = np.sum((hue <= 15) | (hue >= 160))
# 总像素
total = len(hue)

print(f'  绿色调: {green_hue/total*100:.1f}%')
print(f'  蓝色调: {blue_hue/total*100:.1f}%')
print(f'  红色调: {red_hue/total*100:.1f}%')

print('\nDone!')
