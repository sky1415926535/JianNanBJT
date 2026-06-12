#!/usr/bin/env python3
"""
测试最有希望的候选坐标
"""
import cv2
import numpy as np
import sys, os, time, subprocess, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH
from common.config import save_config

def adb_back():
    subprocess.run([ADB_PATH, "shell", "input", "keyevent", "4"],
                  capture_output=True, timeout=5)

def dismiss():
    ADB.tap(960, 500); time.sleep(0.3)
    ADB.tap(1800, 100); time.sleep(0.3)
    ADB.tap(960, 400); time.sleep(0.3)

def check_map(img_path):
    """检查是否进入大地图"""
    img = cv2.imread(img_path)
    if img is None:
        return False, {}
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 检查左侧是否有暗色面板（城镇视图特征）
    left = gray[200:800, 0:100]
    left_dark = np.sum(left < 40) / left.size
    
    # 检查顶部是否有标题栏
    top = gray[0:60, :]
    top_dark = np.sum(top < 50) / top.size
    
    # 中部颜色（大地图偏绿）
    center = img[h//3:2*h//3, w//3:2*w//3]
    avg = np.mean(center, axis=(0,1))
    
    return left_dark < 0.15, {
        'left_dark': left_dark, 'top_dark': top_dark,
        'avg_b': avg[0], 'avg_g': avg[1], 'avg_r': avg[2]
    }

# 最有希望的候选（按可能性排序）
candidates = [
    (67, 529, "左侧面板最大按钮(area=10118)"),
    (1434, 957, "底部右侧最大圆形(area=19980)"),
    (51, 1028, "左下角圆形(area=948, circ=0.723)"),
    (148, 1018, "底部小圆(area=531, circ=0.825)"),
]

print('=' * 60)
print('测试大地图入口候选坐标')
print('=' * 60)

dismiss()
time.sleep(1)

for i, (x, y, desc) in enumerate(candidates):
    print(f'\n--- 测试[{i+1}]: ({x}, {y}) - {desc} ---')
    
    before = f'screenshots/best_{i+1}_before.png'
    ADB.screenshot(save_path=before)
    
    print(f'  点击 ({x}, {y})...')
    ADB.tap(x, y)
    time.sleep(3.0)
    
    after = f'screenshots/best_{i+1}_after.png'
    ADB.screenshot(save_path=after)
    
    # 计算变化
    b_img = cv2.imread(before)
    a_img = cv2.imread(after)
    diff = cv2.absdiff(b_img, a_img)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    change = np.sum(diff_gray > 30) / diff_gray.size
    
    is_map, info = check_map(after)
    
    print(f'  变化率: {change*100:.1f}%')
    print(f'  左侧暗栏: {info.get("left_dark", 0):.3f}')
    print(f'  顶部暗条: {info.get("top_dark", 0):.3f}')
    print(f'  中部色: B={info.get("avg_b",0):.0f} G={info.get("avg_g",0):.0f} R={info.get("avg_r",0):.0f}')
    
    if change > 0.02:
        print(f'  >>> 界面有显著变化!')
        
        if is_map:
            print(f'  ★★★ 进入大地图! ★★★')
            cfg = load_config()
            cfg['prefecture']['big_map_enter_btn'] = {
                'x': x, 'y': y,
                'comment': f'大地图入口 ({desc})'
            }
            save_config(cfg)
            print(f'  config.json 已更新!')
            break
    
    # 返回
    if change > 0.02:
        print(f'  按返回...')
        adb_back()
        time.sleep(1.5)
        dismiss()
        time.sleep(0.5)

print('\nDone!')
