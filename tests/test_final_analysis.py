#!/usr/bin/env python3
"""
在游戏正确加载后，全面分析UI布局，精确定位大地图入口
"""
import cv2
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB

ss_path = 'screenshots/final_game.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR')
    sys.exit(1)

h, w = img.shape[:2]
print(f'全图: {w}x{h}')

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# ======= 1. 精确找内容边界 ========
print('\n======= 1. 游戏内容精确边界 =======')
not_border = gray != 127
content_rows = np.any(not_border, axis=1)
content_cols = np.any(not_border, axis=0)

# 从上往下找第一个有内容的行
y1 = int(np.argmax(content_rows))
# 从下往上找最后一个有内容的行
y2 = int(h - np.argmax(content_rows[::-1]))
# 从左往右找第一个有内容的列
x1 = int(np.argmax(content_cols))
# 从右往左找最后一个有内容的列
x2 = int(w - np.argmax(content_cols[::-1]))

GAME_X1, GAME_Y1, GAME_X2, GAME_Y2 = x1, y1, x2, y2
game_w = GAME_X2 - GAME_X1
game_h = GAME_Y2 - GAME_Y1
print(f'游戏区域: ({GAME_X1},{GAME_Y1}) -> ({GAME_X2},{GAME_Y2})')
print(f'游戏尺寸: {game_w}x{game_h} (宽高比: {game_w/game_h:.2f})')

game = img[GAME_Y1:GAME_Y2, GAME_X1:GAME_X2]
game_gray = cv2.cvtColor(game, cv2.COLOR_BGR2GRAY)

# ======= 2. 左侧暗色面板分析 ========
print('\n======= 2. 左侧UI面板 =======')
# 检查左侧20%是否为暗色面板
left_panel_w = int(game_w * 0.18)
left_panel = game[:, 0:left_panel_w]
lp_gray = game_gray[:, 0:left_panel_w]

# 逐行分析
print('左侧面板垂直颜色分布:')
for y in range(0, game_h, 30):
    row = lp_gray[y:min(y+30, game_h), :]
    avg = np.mean(row)
    bar = '#' * min(int(avg/2), 60)
    if avg < 60:
        print(f'  y={y+GAME_Y1:>4} (内{y:>4}): avg={avg:4.0f} {bar} ★暗色面板')
    elif avg < 100:
        print(f'  y={y+GAME_Y1:>4} (内{y:>4}): avg={avg:4.0f} {bar}')

# Canny边缘
lp_edges = cv2.Canny(lp_gray, 50, 150)
contours, _ = cv2.findContours(lp_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'\n左侧面板按钮 ({len(contours)} 个轮廓):')
btns = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 150:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    if bw < 10 or bh < 10:
        continue
    abs_x = x_c + bw//2 + GAME_X1
    abs_y = y_c + bh//2 + GAME_Y1
    inner_y = y_c + bh//2
    perimeter = cv2.arcLength(c, True)
    circ = 4*np.pi*area/(perimeter*perimeter) if perimeter > 0 else 0
    btns.append({'ax': abs_x, 'ay': abs_y, 'iy': inner_y, 'x': x_c, 'y': y_c, 'w': bw, 'h': bh, 'area': area, 'circ': circ})

btns.sort(key=lambda b: b['iy'])
for i, b in enumerate(btns):
    tag = '●' if b['circ'] > 0.55 else '□'
    print(f'  [{i:>2}] {tag} 屏幕({b["ax"]:>4},{b["ay"]:>4}) 内y={b["iy"]:>4} {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.3f}')

# ======= 3. 底部区域分析 ========
print('\n======= 3. 底部区域分析 =======')
# 检查底部20%
bottom_h = int(game_h * 0.25)
bottom = game[game_h-bottom_h:game_h, :]
b_gray = game_gray[game_h-bottom_h:game_h, :]

print('底部分段:')
for y in range(0, bottom_h, 30):
    row = b_gray[y:min(y+30, bottom_h), :]
    avg = np.mean(row)
    bar = '#' * min(int(avg/2), 60)
    print(f'  y={y+game_h-bottom_h+GAME_Y1:>4}: avg={avg:4.0f} {bar}')

# 底部左侧找印章
bl = game[game_h-bottom_h:game_h, 0:int(game_w*0.3)]
bl_gray = game_gray[game_h-bottom_h:game_h, 0:int(game_w*0.3)]
bl_edges = cv2.Canny(bl_gray, 40, 120)
bl_c, _ = cv2.findContours(bl_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'\n底部左侧轮廓:')
for c in bl_c:
    area = cv2.contourArea(c)
    if area < 200:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    abs_x = x_c + bw//2 + GAME_X1
    abs_y = (game_h - bottom_h + y_c + bh//2) + GAME_Y1
    perimeter = cv2.arcLength(c, True)
    circ = 4*np.pi*area/(perimeter*perimeter) if perimeter > 0 else 0
    print(f'  屏幕({abs_x:>4},{abs_y:>4}) {bw}x{bh} area={area:.0f} circ={circ:.3f}')

# ======= 4. 全游戏按钮检测 ========
print('\n======= 4. 全游戏圆形按钮 =======')
game_edges = cv2.Canny(game_gray, 40, 120)
all_c, _ = cv2.findContours(game_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

circular = []
for c in all_c:
    area = cv2.contourArea(c)
    if area < 200 or area > 50000:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    if bw < 12 or bh < 12:
        continue
    perimeter = cv2.arcLength(c, True)
    circ = 4*np.pi*area/(perimeter*perimeter) if perimeter > 0 else 0
    if circ > 0.5:
        abs_x = x_c + bw//2 + GAME_X1
        abs_y = y_c + bh//2 + GAME_Y1
        circular.append({'ax': abs_x, 'ay': abs_y, 'w': bw, 'h': bh, 'area': area, 'circ': circ})

circular.sort(key=lambda b: b['area'], reverse=True)
print(f'圆形按钮 ({len(circular)} 个, 按面积排序):')
for b in circular[:20]:
    print(f'  屏幕({b["ax"]:>4},{b["ay"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.3f}')

# ======= 5. 保存标注图 ========
debug = game.copy()
debug_full = img.copy()
for b in circular[:30]:
    cx, cy = b['ax']-GAME_X1, b['ay']-GAME_Y1
    r = max(b['w'], b['h'])//2
    cv2.circle(debug, (cx, cy), r, (0, 0, 255), 2)
    cv2.putText(debug, f"{int(b['circ']*100)}", (cx-15, cy-15),
               cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)
    cv2.circle(debug_full, (b['ax'], b['ay']), r, (0, 0, 255), 2)

cv2.imwrite('screenshots/game_circles.png', debug)
cv2.imwrite('screenshots/game_circles_full.png', debug_full)
print(f'\n标注图: screenshots/game_circles.png + screenshots/game_circles_full.png')

# ======= 6. 推荐候选坐标 ========
print('\n======= 6. 推荐大地图入口候选 =======')
# 底部区域的圆形按钮
bottom_circular = [b for b in circular if b['ay'] > GAME_Y1 + game_h * 0.75]
print(f'底部圆形按钮 ({len(bottom_circular)} 个):')
for b in bottom_circular:
    print(f'  屏幕({b["ax"]:>4},{b["ay"]:>4}) area={b["area"]:.0f} circ={b["circ"]:.3f}')

# 左侧面板的圆形按钮
left_circular = [b for b in circular if b['ax'] < GAME_X1 + game_w * 0.25]
print(f'\n左侧圆形按钮 ({len(left_circular)} 个):')
for b in sorted(left_circular, key=lambda x: x['ay']):
    print(f'  屏幕({b["ax"]:>4},{b["ay"]:>4}) area={b["area"]:.0f} circ={b["circ"]:.3f}')

print('\nDone!')
