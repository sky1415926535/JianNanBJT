#!/usr/bin/env python3
"""
在游戏内容区域内重新定位大地图入口按钮
游戏区域: x=480-1420, y=280-800 (约940x520)
"""
import cv2
import numpy as np
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB
from common.adb import ADB_PATH

ss_path = 'screenshots/find_map_btn.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR')
    sys.exit(1)

h, w = img.shape[:2]

# 裁剪游戏内容区域
# 根据分析: x=470-1430, y=270-810 (留余量)
GAME_X1, GAME_Y1 = 470, 270
GAME_X2, GAME_Y2 = 1430, 810

game = img[GAME_Y1:GAME_Y2, GAME_X1:GAME_X2]
gh, gw = game.shape[:2]
print(f'游戏区域: ({GAME_X1},{GAME_Y1}) -> ({GAME_X2},{GAME_Y2})')
print(f'游戏尺寸: {gw}x{gh}')

# 保存游戏区域截图
cv2.imwrite('screenshots/game_region.png', game)

# ======= 分析1: 左侧面板 (游戏内的左侧 x: 0-120) ========
print('\n========== 左侧面板分析 ==========')
left_panel = game[:, 0:120]
lp_h, lp_w = left_panel.shape[:2]

# 检测暗色区域
lp_gray = cv2.cvtColor(left_panel, cv2.COLOR_BGR2GRAY)

# 按行分析
print('左侧面板垂直扫描:')
for y in range(0, lp_h, 25):
    strip = lp_gray[y:min(y+25, lp_h), :]
    avg = np.mean(strip)
    if avg < 70:
        print(f'  y={y+GAME_Y1:>4} (游戏y={y:>4}): avg={avg:5.0f} ★暗色面板')

# Canny边缘检测
lp_edges = cv2.Canny(lp_gray, 40, 120)
contours, _ = cv2.findContours(lp_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'\n左侧面板轮廓 ({len(contours)} 个):')
buttons = []
for c in contours:
    area = cv2.contourArea(c)
    if area < 150:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    cx = x_c + bw // 2 + GAME_X1  # 绝对坐标
    cy = y_c + bh // 2 + GAME_Y1
    gy = y_c + bh // 2  # 游戏内y坐标
    
    perimeter = cv2.arcLength(c, True)
    circ = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
    
    buttons.append({
        'cx': cx, 'cy': cy, 'gy': gy,
        'x': x_c, 'y': y_c, 'w': bw, 'h': bh,
        'area': area, 'circ': circ
    })

buttons.sort(key=lambda b: b['gy'])
for i, b in enumerate(buttons):
    circ_str = f'circ={b["circ"]:.3f}'
    marker = '●圆形' if b['circ'] > 0.6 else ''
    print(f'  [{i}] 绝对({b["cx"]:>4},{b["cy"]:>4}) 游戏y={b["gy"]:>4} {b["w"]}x{b["h"]} area={b["area"]:.0f} {circ_str} {marker}')

# ======= 分析2: 底部面板 (游戏内的底部 y=440-520) ========
print('\n========== 底部面板分析 ==========')
bottom_panel = game[gh-120:gh, :]  # 底部120像素
bp_gray = cv2.cvtColor(bottom_panel, cv2.COLOR_BGR2GRAY)

# 底部左侧区域 (可能是州府印所在)
bottom_left = game[gh-120:gh, 0:200]
bl_gray = cv2.cvtColor(bottom_left, cv2.COLOR_BGR2GRAY)
bl_edges = cv2.Canny(bl_gray, 30, 100)
bl_contours, _ = cv2.findContours(bl_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

print(f'底部左侧轮廓:')
for c in bl_contours:
    area = cv2.contourArea(c)
    if area < 100:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    cx = x_c + GAME_X1  # 绝对x (左侧偏移0-200)
    cy = (gh - 120 + y_c) + GAME_Y1  # 绝对y
    gy = gh - 120 + y_c + bh//2  # 游戏内y
    perimeter = cv2.arcLength(c, True)
    circ = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
    print(f'  绝对({cx:>4},{cy:>4}) 游戏y={gy:>4} {bw}x{bh} area={area:.0f} circ={circ:.3f}')

# ======= 分析3: 全游戏区域轮廓检测 ========
print('\n========== 全游戏区域按钮 ==========')
game_gray = cv2.cvtColor(game, cv2.COLOR_BGR2GRAY)
game_edges = cv2.Canny(game_gray, 40, 120)
all_contours, _ = cv2.findContours(game_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

all_btns = []
for c in all_contours:
    area = cv2.contourArea(c)
    if area < 300 or area > 30000:
        continue
    x_c, y_c, bw, bh = cv2.boundingRect(c)
    if bw < 12 or bh < 12:
        continue
    cx = x_c + bw//2 + GAME_X1
    cy = y_c + bh//2 + GAME_Y1
    perimeter = cv2.arcLength(c, True)
    circ = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
    all_btns.append({
        'cx': cx, 'cy': cy, 'w': bw, 'h': bh,
        'area': area, 'circ': circ
    })

# 分类
circular = [b for b in all_btns if b['circ'] > 0.65 and b['area'] > 500]
rect = [b for b in all_btns if b['circ'] < 0.5 and b['area'] > 500]

print(f'大圆形按钮 (circ>0.65, area>500): {len(circular)} 个')
circular.sort(key=lambda b: b['area'], reverse=True)
for b in circular[:15]:
    print(f'  ({b["cx"]:>4},{b["cy"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.3f}')

print(f'\n大矩形按钮 (circ<0.5, area>500): {len(rect)} 个')
rect.sort(key=lambda b: b['area'], reverse=True)
for b in rect[:15]:
    print(f'  ({b["cx"]:>4},{b["cy"]:>4}) {b["w"]}x{b["h"]} area={b["area"]:.0f} circ={b["circ"]:.3f}')

# ======= 保存标注图 ========
debug_img = game.copy()
for b in circular:
    cv2.circle(debug_img, (b['cx']-GAME_X1, b['cy']-GAME_Y1), 
              max(b['w'], b['h'])//2, (0, 0, 255), 2)
    cv2.putText(debug_img, f"C{int(b['circ']*100)}", 
               (b['cx']-GAME_X1-15, b['cy']-GAME_Y1-10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
for b in rect[:10]:
    cv2.rectangle(debug_img, 
                 (b['cx']-GAME_X1-b['w']//2, b['cy']-GAME_Y1-b['h']//2),
                 (b['cx']-GAME_X1+b['w']//2, b['cy']-GAME_Y1+b['h']//2),
                 (0, 255, 0), 2)

cv2.imwrite('screenshots/game_annotated.png', debug_img)
print(f'\n标注图: screenshots/game_annotated.png')
print('Done!')
