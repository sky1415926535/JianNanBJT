#!/usr/bin/env python3
"""诊断大地图状态，探索寻找宁波府的位置"""

import sys
import time
import logging
from pathlib import Path

sys.path.insert(0, '.')

from common.adb import ADB
from common.ocr import OCREngine, detect_engine

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("Diagnose")

# 初始化 OCR
ocr_engine = detect_engine()
log.info(f"OCR 引擎: {ocr_engine}")
ocr = OCREngine(engine=ocr_engine)


def take_screenshot_and_ocr(label):
    """截图并使用 OCR 识别"""
    print(f"\n{'='*60}")
    print(f"步骤: {label}")
    print('='*60)
    
    # 截图（返回 numpy 数组）
    img = ADB.screenshot(save_path=f'screenshots/diagnose_{label}.png')
    if img is None:
        print("截图失败！")
        return [], []
    
    print(f"截图已保存: screenshots/diagnose_{label}.png")
    
    # OCR 识别
    results = ocr.recognize(img, min_conf=0.3)
    
    if results:
        texts = [(r["text"], r["conf"], r["center"]) for r in results if r["text"]]
        print(f"识别到 {len(texts)} 条文字:")
        for text, conf, center in texts[:20]:  # 只显示前20条
            print(f"  '{text}' 置信度={conf:.2f} 中心={center}")
        
        # 提取纯文本列表
        txts = [t[0] for t in texts]
        centers = [t[2] for t in texts]
        return txts, centers
    else:
        print("未识别到文字")
        return [], []


def is_on_bigmap():
    """检查是否在大地图上"""
    img = ADB.screenshot()
    if img is None:
        return False
    
    results = ocr.recognize(img, min_conf=0.3)
    if results:
        txts = [r["text"] for r in results if r["text"]]
        # 大地图特征：有"府印"按钮，可能有"大地图"标题
        if any('府印' in t for t in txts) or any('大地图' in t for t in txts):
            return True
    return False


def enter_bigmap():
    """进入大地图"""
    print("\n>>> 尝试进入大地图...")
    
    # 先截图检查当前状态
    txts, centers = take_screenshot_and_ocr("enter_bigmap_start")
    
    # 如果检测到"再玩一会"或其他对话框，先处理
    if any('再玩' in t for t in txts):
        print("检测到退出对话框，点击'再玩一会'...")
        ADB.tap(1140, 705)
        time.sleep(1.5)
        txts, centers = take_screenshot_and_ocr("after_dialog_dismiss")
    
    # 如果检测到"府印"，点击进入大地图
    if any('府印' in t for t in txts):
        print("检测到府印，点击...")
        # 找到府印的位置并点击
        img = ADB.screenshot()
        results = ocr.recognize(img, min_conf=0.3)
        for r in results:
            if '府印' in r["text"]:
                cx, cy = r["center"]
                print(f"  点击府印位置: ({cx}, {cy})")
                ADB.tap(cx, cy)
                break
        else:
            # 如果没找到精确位置，使用默认位置
            print("  使用默认位置点击府印")
            ADB.tap(108, 881)
        
        time.sleep(1.5)
        
        # 检查是否出现大地图按钮
        txts2, centers2 = take_screenshot_and_ocr("after_fuyin_click")
        
        # 查找"大地图"按钮
        img2 = ADB.screenshot()
        results2 = ocr.recognize(img2, min_conf=0.3)
        for r in results2:
            if '大地图' in r["text"]:
                cx, cy = r["center"]
                print(f"点击大地图按钮 ({cx}, {cy})...")
                ADB.tap(cx, cy)
                time.sleep(2)
                return True
        
        # 如果没找到"大地图"文字，可能已经在地图上了
        if is_on_bigmap():
            return True
    
    # 如果已经在大地图上
    if is_on_bigmap():
        print("已在大地图上")
        return True
    
    print("无法进入大地图")
    return False


def explore_direction(direction, steps=3):
    """
    向指定方向滚动并OCR检测
    direction: 'up', 'down', 'left', 'right'
    """
    print(f"\n>>> 向{direction}方向探索{steps}步...")
    
    # swipe 坐标 (from_x, from_y, to_x, to_y)
    # 注意：向上滑动 = 从下往上 = (x, high_y) -> (x, low_y)
    swipe_coords = {
        'up':    (640, 500, 640, 200),   # 向上滚动地图
        'down':  (640, 200, 640, 500),   # 向下滚动地图
        'left':  (800, 350, 400, 350),   # 向左滚动地图
        'right': (400, 350, 800, 350),   # 向右滚动地图
    }
    
    coords = swipe_coords[direction]
    
    for i in range(steps):
        print(f"\n  第{i+1}步 - 向{direction}滚动")
        ADB.swipe(coords[0], coords[1], coords[2], coords[3], duration=0.5)
        time.sleep(1.5)
        
        txts, centers = take_screenshot_and_ocr(f"{direction}_step_{i+1}")
        
        # 检查是否找到宁波府
        for idx, txt in enumerate(txts):
            if '宁波' in txt:
                print(f"  ✓ 找到宁波府！文字: {txt}")
                cx, cy = centers[idx]
                print(f"  位置: ({cx}, {cy})")
                return True, cx, cy
        
        # 列出找到的所有州府
        prefectures_found = []
        for txt in txts:
            if ('府' in txt or '州' in txt) and '府印' not in txt and '大地图' not in txt:
                prefectures_found.append(txt)
        
        if prefectures_found:
            print(f"  当前视图找到的州府: {prefectures_found}")
    
    return False, None, None


def swipe_and_find(direction, target='宁波', max_steps=10):
    """
    向指定方向滑动并在每一步检查是否找到目标
    返回: (found, x, y)
    """
    print(f"\n>>> 向{direction}方向滑动寻找'{target}'...")
    
    swipe_coords = {
        'up':    (640, 500, 640, 200),
        'down':  (640, 200, 640, 500),
        'left':  (800, 350, 400, 350),
        'right': (400, 350, 800, 350),
    }
    
    coords = swipe_coords[direction]
    
    for step in range(max_steps):
        print(f"  第{step+1}步：向{direction}滑动")
        ADB.swipe(coords[0], coords[1], coords[2], coords[3], duration=0.5)
        time.sleep(1.5)
        
        # OCR识别
        txts, centers = take_screenshot_and_ocr(f"swipe_{direction}_{step+1}")
        
        # 检查目标
        for idx, txt in enumerate(txts):
            if target in txt:
                print(f"  ✓ 找到！文字: {txt}, 位置: {centers[idx]}")
                return True, centers[idx][0], centers[idx][1]
        
        # 显示当前视图的州府
        prefs = [t for t in txts if '府' in t and '府印' not in t]
        if prefs:
            print(f"  当前视图: {prefs}")
    
    print(f"  未找到'{target}'")
    return False, None, None


def main():
    print("=" * 60)
    print("大地图诊断 - 寻找宁波府")
    print("=" * 60)
    
    # 1. 进入大地图
    if not enter_bigmap():
        print("\n❌ 无法进入大地图，请检查游戏状态")
        print("   确保游戏已进入主界面（有府印按钮）")
        return
    
    print("\n✓ 已进入大地图")
    take_screenshot_and_ocr("bigmap_entered")
    
    # 2. 系统性探索各个方向
    # 根据江南百景图的地图布局，宁波府可能在应天府的右下方
    # 让我们先向右，再向下探索
    print("\n" + "="*60)
    print("开始系统性探索...")
    print("="*60)
    
    # 策略：先向右探索，再向下，然后向左，再向上（螺旋）
    # 每个方向探索3步
    directions = [
        ('right', 4),  # 向右4步
        ('down',  4),  # 向下4步
        ('left',  6),  # 向左6步
        ('up',    6),  # 向上6步
        ('right', 6),  # 向右6步
        ('down',  6),  # 向下6步
    ]
    
    for direction, steps in directions:
        found, x, y = explore_direction(direction, steps=steps)
        if found:
            print(f"\n{'='*60}")
            print(f"✓ 成功找到宁波府！位置: ({x}, {y})")
            print(f"{'='*60}")
            
            # 点击宁波府
            print("点击宁波府...")
            ADB.tap(x, y)
            time.sleep(2)
            
            # 确认切换
            txts, _ = take_screenshot_and_ocr("after_ningbo_click")
            
            # 查找确认按钮（红色按钮）
            print("查找确认按钮...")
            img = ADB.screenshot()
            results = ocr.recognize(img, min_conf=0.3)
            
            # 应该会出现确认对话框
            # 点击屏幕中央偏下的位置（确认按钮通常在这里）
            ADB.tap(640, 550)
            time.sleep(2)
            
            print("\n✓ 已点击确认，应该正在切换州府...")
            take_screenshot_and_ocr("after_confirm")
            
            # TODO: 保存坐标到 config.json
            return
    
    # 如果上面的探索没找到，尝试更大范围的搜索
    print("\n\n" + "="*60)
    print("未找到宁波府，尝试更大范围搜索...")
    print("="*60)
    
    # 回到起始位置（应天府附近）
    # 向左上方滑动回到起点
    for _ in range(5):
        ADB.swipe(400, 350, 800, 350, duration=0.5)  # 向左
        time.sleep(0.5)
    for _ in range(5):
        ADB.swipe(640, 200, 640, 500, duration=0.5)  # 向上
        time.sleep(0.5)
    
    time.sleep(1)
    
    # 现在尝试另一个方向组合
    print("\n尝试2：先向下，再向右...")
    found, x, y = swipe_and_find('down', target='宁波', max_steps=8)
    if not found:
        found, x, y = swipe_and_find('right', target='宁波', max_steps=8)
    
    if found:
        print(f"\n✓ 找到宁波府！点击并切换...")
        ADB.tap(x, y)
        time.sleep(2)
        ADB.tap(640, 550)  # 确认按钮
        return
    
    print("\n" + "="*60)
    print("❌ 未找到宁波府")
    print("可能原因：")
    print("  1. 宁波府尚未解锁")
    print("  2. 需要先从应天府通过剧情解锁")
    print("  3. OCR识别问题（尝试降低置信度阈值）")
    print("  4. 地图缩放级别不对")
    print("="*60)


if __name__ == '__main__':
    main()
