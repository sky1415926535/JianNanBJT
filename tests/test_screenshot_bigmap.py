#!/usr/bin/env python3
"""
标定大地图州府坐标 - 简化版
1. 进入大地图
2. 截图
3. 用 PaddleOCR 识别州府名称
4. 输出坐标
"""
import sys
import time
import cv2
import numpy as np

sys.path.insert(0, 'E:/AI-workspace/JianNanBJT')
from common import ADB, load_config

cfg = load_config()
pref_cfg = cfg.get('prefecture', {})

enter_btn = pref_cfg.get('big_map_enter_btn', {})
menu_btn = pref_cfg.get('big_map_menu_btn', {})
enter_x, enter_y = enter_btn.get('x', 108), enter_btn.get('y', 908)
menu_x, menu_y = menu_btn.get('x', 218), menu_btn.get('y', 389)

def is_on_big_map(img):
    h, w = img.shape[:2]
    lb = img[int(h*0.65):h, 0:int(w*0.13)]
    r = lb[:,:,2].astype(np.float32)
    g = lb[:,:,1].astype(np.float32)
    b = lb[:,:,0].astype(np.float32)
    red_mask = (r > 120) & (r > g*1.2) & (r > b*1.2)
    return np.sum(red_mask) / red_mask.size < 0.08

# 进入大地图
print('进入大地图...')
for attempt in range(3):
    img = ADB.screenshot()
    if img is not None and is_on_big_map(img):
        print('  已在大地图')
        break
    ADB.tap(enter_x, enter_y)
    time.sleep(0.5)
    ADB.tap(menu_x, menu_y)
    time.sleep(3.0)
else:
    print('  警告: 未确认进入大地图')

# 截图
ss_path = 'E:/AI-workspace/JianNanBJT/screenshots/bigmap_calibrate.png'
img = ADB.screenshot(save_path=ss_path)
if img is None:
    print('ERROR: 截图失败')
    sys.exit(1)
print(f'截图已保存: {ss_path}')
print(f'图片尺寸: {img.shape[1]}x{img.shape[0]}')
print()
print('请查看截图，手动记录各州府坐标，然后填入 config.json')
print('州府名称格式: XXX府（如 应天府、苏州府、杭州府、扬州府、徽州府）')
