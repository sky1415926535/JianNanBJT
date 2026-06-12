#!/usr/bin/env python3
"""
手动标定大地图府坐标工具
使用方法：
1. 在模拟器中打开大地图界面
2. 运行此脚本：python manual_calibrate.py
3. 脚本会依次提示你点击每个府的位置
4. 用鼠标点击大地图上的府名/府图标位置
5. 坐标会自动保存到config.json
"""

import sys
import json
import time
import subprocess
from pathlib import Path

# ADB配置（从config.json读取）
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_config(config):
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def adb_tap(device, x, y):
    """通过ADB点击坐标"""
    subprocess.run([
        'D:/leidian/LDPlayer9/adb.exe',
        '-s', device,
        'shell',
        'input', 'tap', str(x), str(y)
    ], capture_output=True)

def adb_screenshot(device, output_path):
    """通过ADB截取屏幕"""
    # 保存到设备
    subprocess.run([
        'D:/leidian/LDPlayer9/adb.exe',
        '-s', device,
        'shell',
        'screencap',
        '-p',
        '/sdcard/bigmap.png'
    ], capture_output=True)
    
    # 拉取到电脑
    subprocess.run([
        'D:/leidian/LDPlayer9/adb.exe',
        '-s', device,
        'pull',
        '/sdcard/bigmap.png',
        output_path
    ], capture_output=True)

def main():
    config = load_config()
    device = config['adb']['device']
    
    print("=" * 60)
    print("江南百景图 - 大地图府坐标手动标定工具")
    print("=" * 60)
    print()
    print("准备步骤：")
    print("1. 请确保模拟器已打开江南百景图")
    print("2. 进入游戏后，打开大地图界面")
    print("3. 确保大地图显示所有府的位置")
    print()
    input("完成后按Enter键继续...")
    
    # 截取当前屏幕
    print("\n正在截取屏幕...")
    screenshot_path = "screenshots/bigmap_current.png"
    Path("screenshots").mkdir(exist_ok=True)
    adb_screenshot(device, screenshot_path)
    print(f"截图已保存到: {screenshot_path}")
    print()
    
    # 需要标定的府
    prefectures_to_calibrate = []
    for name, data in config['prefecture']['prefectures'].items():
        coord = data.get('map_coord', {})
        if coord.get('x', 0) == 0 and coord.get('y', 0) == 0:
            prefectures_to_calibrate.append(name)
    
    if not prefectures_to_calibrate:
        print("✅ 所有府的坐标已配置完成！")
        return
    
    print(f"需要标定的府: {', '.join(prefectures_to_calibrate)}")
    print()
    print("=" * 60)
    print("标定方法（二选一）：")
    print("=" * 60)
    print()
    print("方法A - 图像查看器（推荐）：")
    print("  1. 打开截图: screenshots/bigmap_current.png")
    print("  2. 使用画图/Photoshop等工具查看坐标")
    print("  3. 鼠标移动到府的位置，查看像素坐标")
    print("  4. 在下方输入坐标")
    print()
    print("方法B - 游戏内手动获取：")
    print("  1. 在游戏大地图上，将鼠标悬停在府的位置")
    print("  2. 有些模拟器会显示鼠标坐标")
    print("  3. 记录坐标并在下方输入")
    print()
    
    # 询问用户选择方法
    use_image_viewer = input("是否使用图像查看器方法？(y/n, 默认y): ").strip().lower()
    
    if use_image_viewer != 'n':
        print(f"\n请打开截图: {screenshot_path}")
        print("用图像查看器打开后，鼠标移动到府的位置可以看到坐标")
        input("按Enter继续...")
    
    # 依次标定每个府
    print("\n" + "=" * 60)
    print("开始标定坐标")
    print("=" * 60)
    print()
    
    updated_count = 0
    for name in prefectures_to_calibrate:
        print(f"【{name}】")
        print(f"  请在截图中找到 {name} 的位置")
        print(f"  输入该位置的像素坐标")
        print()
        
        try:
            x_str = input(f"  输入X坐标（或按Enter跳过）: ").strip()
            if not x_str:
                print(f"  ⏭️  跳过 {name}")
                print()
                continue
            
            y_str = input(f"  输入Y坐标: ").strip()
            if not y_str:
                print(f"  ⏭️  跳过 {name}")
                print()
                continue
            
            x = int(x_str)
            y = int(y_str)
            
            # 保存到config
            config['prefecture']['prefectures'][name]['map_coord']['x'] = x
            config['prefecture']['prefectures'][name]['map_coord']['y'] = y
            config['prefecture']['prefectures'][name]['map_coord']['comment'] = f"大地图坐标【已标定】- 手动标定"
            
            print(f"  ✅ {name} 坐标已保存: ({x}, {y})")
            updated_count += 1
            
        except ValueError:
            print(f"  ❌ 坐标格式错误，跳过 {name}")
        except KeyboardInterrupt:
            print("\n\n用户中断，保存已标定的坐标...")
            break
        
        print()
    
    # 保存配置
    if updated_count > 0:
        save_config(config)
        print("=" * 60)
        print(f"✅ 已保存 {updated_count} 个府的坐标到 config.json")
        print("=" * 60)
        
        # 显示所有已配置的府
        print("\n当前所有府的坐标：")
        for name, data in config['prefecture']['prefectures'].items():
            coord = data.get('map_coord', {})
            x = coord.get('x', 0)
            y = coord.get('y', 0)
            comment = coord.get('comment', '')
            status = "✅" if x != 0 and y != 0 else "❌"
            print(f"  {status} {name}: ({x}, {y}) - {comment}")
    else:
        print("\n未更新任何坐标")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已退出")
        sys.exit(0)
