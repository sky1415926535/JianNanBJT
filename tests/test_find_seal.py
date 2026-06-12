#!/usr/bin/env python3
"""
通过颜色分割定位"州府印"图章
州府印通常是一个红色/橙色的圆形图章，位于左下角
"""
import cv2
import numpy as np
import sys, os, time, subprocess, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH
from common.paths import SCREENSHOT_DIR

def adb_back():
    subprocess.run(
        [ADB_PATH, "shell", "input", "keyevent", "4"],
        capture_output=True, timeout=5
    )

# 确保在城镇视图
adb_back()
time.sleep(1.5)

# 关闭弹窗
print('关闭弹窗...')
ADB.tap(960, 500); time.sleep(0.3)
ADB.tap(1800, 100); time.sleep(0.3)
ADB.tap(960, 400); time.sleep(0.3)
ADB.tap(960, 900); time.sleep(0.3)  # 也点一下下面，关闭浮窗

# 截图
ss_path = 'screenshots/find_seal.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR: 截图失败')
    sys.exit(1)

h, w = img.shape[:2]
print(f'图片尺寸: {w}x{h}')

# 转换为 HSV 色彩空间用于颜色分割
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# ============ 方法1: 红色/橙色检测 ============
print('\n========== 方法1: 红色/橙色圆形检测 ==========')

# 红色有两个范围（绕HSV一圈）
# 橙红色: H in [0, 15] or [160, 180]
lower_red1 = np.array([0, 80, 80])
upper_red1 = np.array([15, 255, 255])
lower_red2 = np.array([160, 80, 80])
upper_red2 = np.array([180, 255, 255])

mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
red_mask = cv2.bitwise_or(mask1, mask2)

# 也检测橙色/棕色
lower_orange = np.array([10, 60, 60])
upper_orange = np.array([25, 255, 255])
orange_mask = cv2.inRange(hsv, lower_orange, upper_orange)

# 合并红色和橙色
color_mask = cv2.bitwise_or(red_mask, orange_mask)

# 形态学处理
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, kernel)
color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, kernel)

# 保存掩码
cv2.imwrite('screenshots/find_seal_red_mask.png', color_mask)

# 查找轮廓
contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'红色/橙色区域: {len(contours)} 个')
red_objects = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 100:
        continue
    x, y_c, bw, bh = cv2.boundingRect(c)
    cx, cy = x + bw // 2, y_c + bh // 2
    
    # 圆形度
    perimeter = cv2.arcLength(c, True)
    circularity = 0
    if perimeter > 0:
        circularity = 4 * np.pi * area / (perimeter * perimeter)
    
    red_objects.append({
        'cx': cx, 'cy': cy,
        'x': x, 'y': y_c, 'w': bw, 'h': bh,
        'area': area, 'circularity': circularity
    })

red_objects.sort(key=lambda o: o['area'], reverse=True)
print(f'  有效红色对象 ({len(red_objects)} 个):')
for o in red_objects[:20]:
    print(f'  ({o["cx"]:>4}, {o["cy"]:>4})  {o["w"]}x{o["h"]}  area={o["area"]:.0f}  circ={o["circularity"]:.3f}')

# ============ 方法2: 分析左下角区域找圆形图章 ============
print('\n========== 方法2: 左下角专门分析 ==========')

# 聚焦左下角 (x: 0-250, y: 800-1080)
bottom_left = img[800:1080, 0:250]
bl_h, bl_w = bottom_left.shape[:2]

# 转换为灰度
bl_gray = cv2.cvtColor(bottom_left, cv2.COLOR_BGR2GRAY)

# 检测圆形 - 霍夫圆检测
circles = cv2.HoughCircles(
    bl_gray, cv2.HOUGH_GRADIENT,
    dp=1.2, minDist=30,
    param1=50, param2=30,
    minRadius=20, maxRadius=80
)

if circles is not None:
    circles = np.uint16(np.around(circles))
    print(f'霍夫圆检测: {len(circles[0])} 个圆')
    for i, circle in enumerate(circles[0, :]):
        cx, cy, r = circle
        # 相对于全图的坐标
        abs_cx = cx
        abs_cy = cy + 800
        print(f'  圆{i}: ({abs_cx}, {abs_cy}) 半径={r}')
        
        # 检查圆的颜色
        mask = np.zeros((bl_h, bl_w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), r-2, 255, -1)
        mean_color = cv2.mean(bottom_left, mask=mask)
        print(f'    颜色: B={mean_color[0]:.0f} G={mean_color[1]:.0f} R={mean_color[2]:.0f}')
else:
    print('霍夫圆检测: 未找到圆')

# ============ 方法3: 模板匹配 - 找明显的圆形按钮 ============
print('\n========== 方法3: 边缘检测找大号圆形 ==========')

# Canny边缘
bl_edges = cv2.Canny(bl_gray, 30, 100)
contours2, _ = cv2.findContours(bl_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

large_circles = []
for c in contours2:
    area = cv2.contourArea(c)
    if area < 300 or area > 15000:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    cx = x_c
    cy = y_c + 800  # 绝对坐标
    
    perimeter = cv2.arcLength(c, True)
    circularity = 0
    if perimeter > 0:
        circularity = 4 * np.pi * area / (perimeter * perimeter)
    
    # 检查是否是圆形
    if circularity > 0.5:
        large_circles.append({
            'cx': cx, 'cy': cy,
            'w': bw, 'h': bh, 'area': area, 'circ': circularity
        })

large_circles.sort(key=lambda o: o['area'], reverse=True)
print(f'大圆形对象 ({len(large_circles)} 个):')
for o in large_circles[:10]:
    print(f'  ({o["cx"]:>4}, {o["cy"]:>4})  {o["w"]}x{o["h"]}  area={o["area"]:.0f}  circ={o["circ"]:.3f}')

# ============ 方法4: 直接找所有有趣的候选 ============
print('\n========== 方法4: 综合候选坐标 ==========')

# 把所有候选合并分析
all_candidates = []

# 红色对象
for o in red_objects:
    if o['area'] > 200:
        all_candidates.append(('红色', o['cx'], o['cy'], o['area'], o['circularity']))

# 大圆形
for o in large_circles:
    all_candidates.append(('大圆', o['cx'], o['cy'], o['area'], o['circ']))

# 去重
seen = set()
unique = []
for typ, cx, cy, area, circ in all_candidates:
    key = (round(cx/5)*5, round(cy/5)*5)
    if key not in seen:
        seen.add(key)
        unique.append((typ, cx, cy, area, circ))

unique.sort(key=lambda x: x[4], reverse=True)  # 按圆形度排序
print(f'候选 (按圆形度排序):')
for typ, cx, cy, area, circ in unique[:15]:
    print(f'  [{typ}] ({cx:>4}, {cy:>4})  area={area:.0f}  circ={circ:.3f}')

# 保存标注图
debug_img = img.copy()
for o in red_objects[:30]:
    cv2.circle(debug_img, (o['cx'], o['cy']), max(o['w'], o['h'])//2, (0, 0, 255), 2)
    cv2.putText(debug_img, f"R{int(o['circularity']*100)}", (o['x'], o['y']-5),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
for o in large_circles[:30]:
    cv2.rectangle(debug_img, (o['cx']-o['w']//2, o['cy']-o['h']//2),
                 (o['cx']+o['w']//2, o['cy']+o['h']//2), (0, 255, 0), 2)
    cv2.putText(debug_img, f"C{int(o['circ']*100)}", (o['cx']-o['w']//2, o['cy']-o['h']//2-5),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

cv2.imwrite('screenshots/find_seal_debug.png', debug_img)
print(f'\n调试图保存到: screenshots/find_seal_debug.png')
print('Done!')
