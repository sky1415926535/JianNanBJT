#!/usr/bin/env python3
"""
在游戏区域内测试左下角坐标，寻找大地图入口
游戏区域: x=470-1430, y=270-810 (960x540)
州府印预期在游戏左下角: 游戏坐标(30~80, 460~510) → 屏幕坐标(500~550, 730~780)
"""
import cv2
import numpy as np
import sys, os, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ADB, load_config
from common.adb import ADB_PATH

GAME_X1, GAME_Y1 = 470, 270

def adb_back():
    subprocess.run([ADB_PATH, "shell", "input", "keyevent", "4"],
                  capture_output=True, timeout=5)

def dismiss_popups():
    print('  关闭弹窗...')
    ADB.tap(960, 500); time.sleep(0.3)
    ADB.tap(1800, 100); time.sleep(0.3)
    ADB.tap(960, 900); time.sleep(0.3)
    ADB.tap(960, 500); time.sleep(0.3)

def check_if_changed(before_path, after_path):
    """检查截图是否有显著变化"""
    before = cv2.imread(before_path)
    after = cv2.imread(after_path)
    if before is None or after is None:
        return 0
    diff = cv2.absdiff(before, after)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    changed = np.sum(diff_gray > 30) / diff_gray.size
    return changed

# 候选坐标 (屏幕坐标, 对应游戏内坐标)
# 游戏区域左下角: 游戏内(0-150, 400-540) → 屏幕(470-620, 670-810)
candidates = [
    # 左下角印章位置
    (500, 770, "左下角-偏左"),
    (530, 770, "左下角-偏中"),
    (560, 770, "左下角-偏右"),
    (515, 745, "左下角-偏上左"),
    (545, 745, "左下角-偏上中"),
    # 如果印章在更下方
    (500, 790, "左下角-最下左"),
    (530, 790, "左下角-最下中"),
    # 可能是一个独立的面板/按钮
    (500, 730, "左下角-上左"),
    (530, 730, "左下角-上中"),
    # 最后一种可能 - 地图图标在左侧面板上（不是印章，而是地图图标）
    (495, 690, "左侧面板-地图图标"),
    (495, 660, "左侧面板-建筑图标"),
    (495, 630, "左侧面板-第三个图标"),
]

print('=' * 60)
print('在游戏区域内测试坐标')
print(f'游戏区域: ({GAME_X1},{GAME_Y1}) ~ ({GAME_X1+960},{GAME_Y1+540})')
print('=' * 60)

# 先确保在城镇视图
adb_back()
time.sleep(1.0)
dismiss_popups()
time.sleep(1.0)

# 基准截图
baseline_path = 'screenshots/game_baseline.png'
ADB.screenshot(save_path=baseline_path)
print(f'\n基准截图: {baseline_path}')

found = False

for i, (x, y, desc) in enumerate(candidates):
    if found:
        break
    
    game_x = x - GAME_X1
    game_y = y - GAME_Y1
    print(f'\n--- 测试[{i+1}/{len(candidates)}]: 屏幕({x},{y}) 游戏内({game_x},{game_y}) - {desc} ---')
    
    before = f'screenshots/game_test_{i+1}_before.png'
    ADB.screenshot(save_path=before)
    
    print(f'  点击...')
    ADB.tap(x, y)
    time.sleep(3.0)
    
    after = f'screenshots/game_test_{i+1}_after.png'
    ADB.screenshot(save_path=after)
    
    # 分析变化
    change_pct = check_if_changed(before, after)
    
    # 分析后截图
    after_img = cv2.imread(after)
    if after_img is not None:
        h_img, w_img = after_img.shape[:2]
        # 检查是否为大地图: 看颜色分布
        center = after_img[h_img//3:2*h_img//3, w_img//3:2*w_img//3]
        avg = np.mean(center, axis=(0, 1))
        # 检查左侧暗色竖栏
        left = after_img[200:800, 0:100]
        left_gray = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        left_dark = np.sum(left_gray < 40) / left_gray.size
        
        # 检查游戏区域是否改变
        game_region = after_img[GAME_Y1:GAME_Y1+540, GAME_X1:GAME_X1+960]
        game_gray = cv2.cvtColor(game_region, cv2.COLOR_BGR2GRAY)
        game_std = np.std(game_gray)
        
        print(f'  变化率: {change_pct*100:.1f}%')
        print(f'  中部平均色: B={avg[0]:.0f} G={avg[1]:.0f} R={avg[2]:.0f}')
        print(f'  左侧暗栏: {left_dark:.3f}')
        print(f'  游戏区标准差: {game_std:.1f}')
        
        # 判断：如果变化大、没有左侧暗栏、游戏区有内容 → 可能是大地图
        if change_pct > 0.05 and left_dark < 0.15 and game_std > 20:
            print(f'  ★★★ 可能是大地图! ★★★')
            found = True
            
            # 更新config
            cfg = load_config()
            cfg['prefecture']['big_map_enter_btn'] = {
                'x': x, 'y': y,
                'comment': f'大地图入口 ({desc}, 游戏内({game_x},{game_y}))'
            }
            from common.config import save_config
            save_config(cfg)
            print(f'  config.json 已更新! big_map_enter_btn = ({x}, {y})')
            break
    
    # 按返回（防止进入奇怪界面）
    if not found and change_pct > 0.1:
        print(f'  变化较大，按返回...')
        adb_back()
        time.sleep(1.5)
        dismiss_popups()
        time.sleep(1.0)

if not found:
    print('\n未找到大地图入口。')
    print('可能需要更广泛的搜索或不同的入口方式。')

print('\nDone!')
