#!/usr/bin/env python3
"""多方向大地图扫描 - 从默认视图向上下左右四个方向扩展"""
import subprocess, json, time, os
from pathlib import Path
from datetime import datetime

# 配置
ADB = "D:/leidian/LDPlayer9/adb.exe"
DEVICE = "emulator-5554"
OUT_DIR = Path(__file__).parent / "screenshots" / "map_full"
STEP_X, STEP_Y = 1056, 594
RINGS = 1  # 向每个方向扩展1圈

OUT_DIR.mkdir(parents=True, exist_ok=True)

def adb(cmd):
    return subprocess.run(f'{ADB} -s {DEVICE} {cmd}', shell=True, capture_output=True, text=True)

def swipe(x1, y1, x2, y2):
    adb(f'shell input swipe {x1} {y1} {x2} {y2} 800')

def screenshot(name):
    path = OUT_DIR / f"{name}.png"
    adb(f'shell screencap -p /sdcard/{name}.png')
    adb(f'pull /sdcard/{name}.png "{path}"')
    adb(f'shell rm /sdcard/{name}.png')
    return str(path)

print("=" * 60)
print("多方向大地图扫描")
print("=" * 60)

# 先回到默认视图 - 不做任何滚动
print("\n⚠️  请确保大地图已打开（在默认位置），等待 3 秒...")
time.sleep(3)

# 从默认位置开始
print("\n[1] 默认位置截图...")
screenshot("center_default")
print("  ✓ center_default (默认视图)")

# 向上扫描
print("\n[2] 向上扫描...")
for ring in range(1, RINGS + 1):
    for _ in range(ring):
        swipe(960, 540, 960, 540 + STEP_Y)  # 向上拖
        time.sleep(1.5)
    screenshot(f"up_{ring}")
    print(f"  ✓ up_{ring}")
# 回到默认
for ring in range(RINGS):
    for _ in range(ring + 1):
        swipe(960, 540, 960, 540 - STEP_Y)  # 向下拖回
        time.sleep(1.5)
time.sleep(1)

# 向下扫描
print("\n[3] 向下扫描...")
for ring in range(1, RINGS + 1):
    for _ in range(ring):
        swipe(960, 540, 960, 540 - STEP_Y)
        time.sleep(1.5)
    screenshot(f"down_{ring}")
    print(f"  ✓ down_{ring}")
# 回到默认
for ring in range(RINGS):
    for _ in range(ring + 1):
        swipe(960, 540, 960, 540 + STEP_Y)
        time.sleep(1.5)
time.sleep(1)

# 向左扫描
print("\n[4] 向左扫描...")
for ring in range(1, RINGS + 1):
    for _ in range(ring):
        swipe(960, 540, 960 + STEP_X, 540)
        time.sleep(1.5)
    screenshot(f"left_{ring}")
    print(f"  ✓ left_{ring}")
# 回到默认
for ring in range(RINGS):
    for _ in range(ring + 1):
        swipe(960, 540, 960 - STEP_X, 540)
        time.sleep(1.5)
time.sleep(1)

# 向右扫描
print("\n[5] 向右扫描...")
for ring in range(1, RINGS + 1):
    for _ in range(ring):
        swipe(960, 540, 960 - STEP_X, 540)
        time.sleep(1.5)
    screenshot(f"right_{ring}")
    print(f"  ✓ right_{ring}")
# 回到默认
for ring in range(RINGS):
    for _ in range(ring + 1):
        swipe(960, 540, 960 + STEP_X, 540)
        time.sleep(1.5)

print(f"\n✅ 扫描完成！共 {1 + RINGS * 4} 张截图")
print(f"   保存位置: {OUT_DIR}")
