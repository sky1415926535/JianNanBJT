#!/usr/bin/env python3
"""
================================================================================
大地图分片探索 + 府坐标自动标定工具 (v1.0)
================================================================================

【背景问题】
  大地图尺寸超过屏幕(1920x1080)，无法一次截取完整地图。
  需要通过系统化的分片截图 + 区域检测 + 用户映射来标定所有府的坐标。

【工作流程】
  1. 扫描阶段: 系统化滚动地图，在N个位置截图
  2. 检测阶段: 对每张截图运行MSER检测，标注文字区域
  3. 映射阶段: 用户查看每张标注图，输入"区域编号→府名"映射
  4. 保存阶段: 将所有府的(滚动状态, 屏幕坐标)写入config.json

【使用方法】
  # 扫描大地图（在N个位置截图）
  python map_explorer.py scan
  
  # 检测文字区域（为每张截图生成标注图片）
  python map_explorer.py detect
  
  # 交互式映射（一边看标注图一边输入区域编号）
  python map_explorer.py map
  
  # 一键完成全部流程
  python map_explorer.py all

【依赖】
  pip install opencv-python numpy
"""

import os
import sys
import time
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np

# ============================================================
# 路径常量
# ============================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
MAP_DIR = SCRIPT_DIR / "screenshots" / "map_grid"
MAP_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 配置加载
# ============================================================
def load_config():
    with open(SCRIPT_DIR / "config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(SCRIPT_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_grid_data():
    """加载网格扫描数据"""
    grid_file = MAP_DIR / "grid_data.json"
    if grid_file.exists():
        with open(grid_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"positions": [], "screenshots": [], "regions_by_position": {}}

def save_grid_data(data):
    grid_file = MAP_DIR / "grid_data.json"
    with open(grid_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# ADB 操作
# ============================================================
def get_adb():
    config = load_config()
    adb_path = config["adb"]["path"]
    device = config["adb"]["device"]
    return adb_path, device

def adb_screenshot(output_path):
    """截取当前屏幕"""
    adb_path, device = get_adb()
    # 截图到设备
    subprocess.run([adb_path, "-s", device, "shell", "screencap", "-p", 
                    "/sdcard/map_screen.png"], capture_output=True, check=True)
    # 拉到本地
    result = subprocess.run([adb_path, "-s", device, "pull", 
                             "/sdcard/map_screen.png", str(output_path)], 
                            capture_output=True, text=True)
    return result.returncode == 0

def adb_swipe(x1, y1, x2, y2, duration=500):
    """模拟滑动（拖动地图）"""
    adb_path, device = get_adb()
    subprocess.run([adb_path, "-s", device, "shell", "input", "swipe",
                    str(x1), str(y1), str(x2), str(y2), str(duration)],
                   capture_output=True, check=True)

def adb_tap(x, y):
    """模拟点击"""
    adb_path, device = get_adb()
    subprocess.run([adb_path, "-s", device, "shell", "input", "tap",
                    str(x), str(y)], capture_output=True, check=True)

# ============================================================
# MSER 文字区域检测
# ============================================================
def detect_text_regions(img_path, min_area=1500, max_area=20000):
    """
    检测图片中的文字区域
    返回: list of {id, bbox, center, area}
    """
    img = cv2.imread(str(img_path))
    if img is None:
        return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    mser = cv2.MSER_create(
        delta=5,
        min_area=min_area,
        max_area=max_area,
        max_variation=0.25,
        min_diversity=0.2
    )
    
    regions, bboxes = mser.detectRegions(gray)
    
    results = []
    for i, bbox in enumerate(bboxes):
        x, y, w, h = bbox
        results.append({
            'id': i,
            'bbox': [int(x), int(y), int(w), int(h)],
            'center': [int(x + w//2), int(y + h//2)],
            'area': int(w * h)
        })
    
    # 按面积排序
    results.sort(key=lambda r: r['area'], reverse=True)
    for i, r in enumerate(results):
        r['id'] = i
    
    return results

def annotate_image(img_path, regions, output_path):
    """在图片上标注文字区域"""
    img = cv2.imread(str(img_path))
    if img is None:
        return False
    
    annotated = img.copy()
    
    for region in regions:
        x, y, w, h = region['bbox']
        cx, cy = region['center']
        
        # 边框颜色根据面积：大区域=绿色，小区域=蓝色
        if region['area'] > 5000:
            color = (0, 255, 0)  # 绿色 = 可能是府名
        elif region['area'] > 2000:
            color = (255, 255, 0)  # 黄色 = 中等文字
        else:
            color = (255, 0, 0)  # 蓝色 = 小文字
        
        cv2.rectangle(annotated, (x, y), (x+w, y+h), color, 2)
        cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)
        cv2.putText(annotated, f"[{region['id']:02d}]", (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
    
    cv2.imwrite(str(output_path), annotated)
    return True

# ============================================================
# 阶段1: 扫描 - 网格化截取地图分片
# ============================================================
def scan_map_grid(rows=3, cols=3, skip_confirm=False):
    """
    在大地图上进行网格扫描，截取多个分片
    
    策略:
    - 首先滚到地图的最边角（向左上和右下分别滚到极限）
    - 然后按网格逐步扫描
    
    步骤:
    1. 滚到地图左上角（多次向上+向左滑动）
    2. 按 colsxrows 网格拍照
    3. 每次网格移动 = 向右滑一个屏幕宽度
    4. 每行结束后向下滑一个屏幕高度，重新从左边开始
    """
    config = load_config()
    screen_w = config["screen"]["width"]
    screen_h = config["screen"]["height"]
    
    # 网格参数
    # 一次滑动 = 约屏幕的60%（减少重叠区域）
    swipe_step_x = int(screen_w * 0.55)
    swipe_step_y = int(screen_h * 0.55)
    
    print("=" * 60)
    print(f"大地图网格扫描 ({rows}x{cols})")
    print("=" * 60)
    print()
    print(f"屏幕: {screen_w}x{screen_h}")
    print(f"滑动步长: {swipe_step_x}x{swipe_step_y}")
    print(f"网格: {rows}行 x {cols}列")
    print()
    print("⚠️  重要: 请在游戏中打开大地图界面！")
    print("   大地图通常通过点击左下角红色印章打开")
    if not skip_confirm:
        input("   确认后按 Enter 继续...")
    else:
        print("   自动跳过确认（--yes），等待3秒后开始...")
        time.sleep(3)
    
    positions = []
    screenshots = []
    
    # ============================================================
    # 步骤1: 滚到左上角（地图起点）
    # ============================================================
    print("\n[1/4] 正在滚动到地图左上角...")
    # 多次向上+向左滑动确保到达边界
    for i in range(6):
        adb_swipe(screen_w//2, screen_h//3, screen_w//2, screen_h*2//3, 300)
        time.sleep(0.3)
    for i in range(6):
        adb_swipe(screen_w*2//3, screen_h//2, screen_w//3, screen_h//2, 300)
        time.sleep(0.3)
    time.sleep(0.5)
    print("  ✓ 已到达左上角起点")
    
    # ============================================================
    # 步骤2: 逐行逐列拍照
    # ============================================================
    print(f"\n[2/4] 开始逐格扫描 {rows}x{cols} 网格...")
    
    for row in range(rows):
        for col in range(cols):
            idx = row * cols + col
            position_name = f"r{row}_c{col}"
            
            # 拍照
            screenshot_path = MAP_DIR / f"{position_name}.png"
            adb_screenshot(screenshot_path)
            
            positions.append({
                "idx": idx,
                "name": position_name,
                "row": row,
                "col": col,
                "scroll_x": col * swipe_step_x,
                "scroll_y": row * swipe_step_y,
            })
            screenshots.append(str(screenshot_path))
            
            progress = (idx + 1) / (rows * cols) * 100
            print(f"  [{idx+1}/{rows*cols}] {position_name} ✓ ({progress:.0f}%)")
            
            if col < cols - 1:
                # 向右滚动
                adb_swipe(screen_w*3//4, screen_h//2, screen_w//4, screen_h//2, 400)
                time.sleep(0.4)
            else:
                # 每行结束，回到左边，向下滚动
                if row < rows - 1:
                    # 回到左边
                    for c in range(cols - 1):
                        adb_swipe(screen_w//4, screen_h//2, screen_w*3//4, screen_h//2, 400)
                        time.sleep(0.3)
                    # 向下滚动
                    adb_swipe(screen_w//2, screen_h*3//4, screen_w//2, screen_h//4, 400)
                    time.sleep(0.5)
    
    # ============================================================
    # 步骤3: 保存网格数据
    # ============================================================
    print(f"\n[3/4] 保存网格数据...")
    grid_data = {
        "timestamp": datetime.now().isoformat(),
        "screen_size": [screen_w, screen_h],
        "grid": {"rows": rows, "cols": cols},
        "swipe_step": [swipe_step_x, swipe_step_y],
        "positions": positions,
        "screenshots": screenshots,
        "regions_by_position": {}
    }
    save_grid_data(grid_data)
    print(f"  ✓ 已保存到: {MAP_DIR}/grid_data.json")
    
    # ============================================================
    # 步骤4: 总结
    # ============================================================
    print(f"\n[4/4] 扫描完成！共 {len(screenshots)} 张截图")
    print()
    print("=" * 60)
    print("下一步: 运行区域检测")
    print("=" * 60)
    print("  python map_explorer.py detect")
    print()

# ============================================================
# 阶段2: 检测 - 对每张截图进行MSER文字区域检测
# ============================================================
def detect_all_regions():
    """对所有截图进行MSER检测"""
    grid_data = load_grid_data()
    
    if not grid_data["screenshots"]:
        print("❌ 没有找到截图，请先运行: python map_explorer.py scan")
        return
    
    print("=" * 60)
    print("MSER 文字区域检测")
    print("=" * 60)
    print()
    
    regions_by_position = {}
    total_regions = 0
    
    for i, screenshot_path in enumerate(grid_data["screenshots"]):
        pos = grid_data["positions"][i]
        pos_name = pos["name"]
        
        print(f"[{i+1}/{len(grid_data['screenshots'])}] 检测: {pos_name}")
        
        # 检测文字区域
        regions = detect_text_regions(screenshot_path)
        
        # 保存标注图片
        annotated_path = MAP_DIR / f"{pos_name}_annotated.png"
        annotate_image(screenshot_path, regions, annotated_path)
        
        regions_by_position[pos_name] = {
            "screenshot": screenshot_path,
            "annotated": str(annotated_path),
            "total_regions": len(regions),
            "regions": regions
        }
        
        total_regions += len(regions)
        print(f"  → 检测到 {len(regions)} 个区域")
        print(f"  → 标注图: {annotated_path.name}")
    
    # 保存检测结果
    grid_data["regions_by_position"] = regions_by_position
    save_grid_data(grid_data)
    
    print(f"\n✅ 检测完成！共 {total_regions} 个文字区域")
    print()
    print("=" * 60)
    print("下一步: 交互式映射")
    print("=" * 60)
    print("  python map_explorer.py map")
    print()

# ============================================================
# 阶段3: 映射 - 用户将区域编号映射到府名
# ============================================================
def map_regions_to_prefectures():
    """交互式地将检测到的区域映射到府名"""
    config = load_config()
    grid_data = load_grid_data()
    
    if not grid_data.get("regions_by_position"):
        print("❌ 没有检测结果，请先运行: python map_explorer.py detect")
        return
    
    prefectures = config["prefecture"]["prefectures"]
    regions_by_pos = grid_data["regions_by_position"]
    
    # 找出未标定的府
    uncalibrated = {}
    for name, data in prefectures.items():
        coord = data.get("map_coord", {})
        if coord.get("x", 0) == 0 and coord.get("y", 0) == 0:
            uncalibrated[name] = data
    
    if not uncalibrated:
        print("✅ 所有府的坐标已配置完成！")
        return
    
    print("=" * 60)
    print("府名 ↔ 区域 交互式映射")
    print("=" * 60)
    print()
    print(f"待标定府: {len(uncalibrated)} 个")
    print(f"   {', '.join(uncalibrated.keys())}")
    print()
    print("使用方法:")
    print("  1. 打开标注图片: screenshots/map_grid/r0_c0_annotated.png (等)")
    print("  2. 找到府名所在的区域编号（如 [12]）")
    print("  3. 在下方输入该编号")
    print()
    print("快捷命令:")
    print("  list <位置名>     - 列出某个截图中的所有区域")
    print("  show <位置名>     - 显示某个截图的详细信息")
    print("  skip              - 跳过一个府")
    print("  help              - 显示帮助")
    print("  done              - 保存并退出")
    print()
    
    updated_count = 0
    
    for name in uncalibrated:
        print(f"\n{'='*40}")
        print(f"【{name}】")
        print(f"{'='*40}")
        print(f"  请在各标注图中找到 '{name}' 对应的区域")
        print(f"  标注图位置: screenshots/map_grid/")
        print()
        print(f"  输入格式: <位置名> <区域编号>")
        print(f"  例如: r0_c0 12")
        print(f"  或直接输入 skip 跳过")
        print()
        
        while True:
            cmd = input(f"  [{name}] > ").strip()
            
            if cmd.lower() == "skip":
                print(f"  ⏭️  跳过 {name}")
                break
            
            if cmd.lower() == "done":
                print("  💾 保存并退出...")
                # 保存到config
                save_config(config)
                return
            
            if cmd.lower().startswith("list"):
                parts = cmd.split()
                pos_name = parts[1] if len(parts) > 1 else None
                if pos_name and pos_name in regions_by_pos:
                    _list_regions(pos_name, regions_by_pos)
                else:
                    print("  可用位置: " + ", ".join(regions_by_pos.keys()))
                continue
            
            if cmd.lower() == "help":
                print("  命令: list <位置>, show <位置>, skip, done, <位置> <编号>")
                continue
            
            # 解析: <位置名> <区域编号>
            parts = cmd.split()
            if len(parts) >= 2:
                pos_name = parts[0]
                try:
                    region_id = int(parts[1])
                except ValueError:
                    print("  ❌ 区域编号必须是数字")
                    continue
                
                if pos_name not in regions_by_pos:
                    print(f"  ❌ 未知位置: {pos_name}")
                    print(f"  可用: {', '.join(regions_by_pos.keys())}")
                    continue
                
                region_list = regions_by_pos[pos_name]["regions"]
                if region_id < 0 or region_id >= len(region_list):
                    print(f"  ❌ 区域编号超出范围 (0-{len(region_list)-1})")
                    continue
                
                region = region_list[region_id]
                x, y = region["center"]
                
                # 保存坐标
                prefectures[name]["map_coord"]["x"] = x
                prefectures[name]["map_coord"]["y"] = y
                prefectures[name]["map_coord"]["comment"] = f"大地图坐标【已标定】- 分片扫描 ({pos_name}, 区域{region_id})"
                
                # 还要记录位置信息，便于后期导航
                if "grid_position" not in prefectures[name]:
                    prefectures[name]["grid_position"] = {}
                prefectures[name]["grid_position"] = {
                    "name": pos_name,
                    "row": grid_data["positions"][next(
                        i for i, p in enumerate(grid_data["positions"]) 
                        if p["name"] == pos_name
                    )]["row"],
                    "col": grid_data["positions"][next(
                        i for i, p in enumerate(grid_data["positions"]) 
                        if p["name"] == pos_name
                    )]["col"],
                    "scroll_x": grid_data["positions"][next(
                        i for i, p in enumerate(grid_data["positions"]) 
                        if p["name"] == pos_name
                    )]["scroll_x"],
                    "scroll_y": grid_data["positions"][next(
                        i for i, p in enumerate(grid_data["positions"]) 
                        if p["name"] == pos_name
                    )]["scroll_y"],
                    "region_id": region_id
                }
                
                print(f"  ✅ {name}: ({x}, {y}) / 位置={pos_name}")
                updated_count += 1
                break
            else:
                print("  ❌ 格式错误，请使用: <位置名> <区域编号>")
    
    # 保存配置
    save_config(config)
    
    print(f"\n{'='*60}")
    print(f"✅ 已更新 {updated_count} 个府的坐标")
    print(f"{'='*60}")
    print()
    
    # 显示所有府状态
    _show_all_prefectures(config)

def _list_regions(pos_name, regions_by_pos):
    """列出指定位置的所有区域"""
    data = regions_by_pos[pos_name]
    regions = data["regions"]
    
    print(f"\n  位置 {pos_name}: {len(regions)} 个区域")
    print(f"  {'编号':<6} {'中心坐标':<16} {'宽x高':<14} {'面积':<8}")
    print(f"  {'-'*45}")
    
    for r in regions[:30]:  # 只显示前30个
        c = r["center"]
        b = r["bbox"]
        print(f"  [{r['id']:02d}]    ({c[0]:>4}, {c[1]:>4})    {b[2]:>4}x{b[3]:<4}    {r['area']:>6}")

def _show_all_prefectures(config):
    """显示所有府的标定状态"""
    prefectures = config["prefecture"]["prefectures"]
    print("当前所有府坐标：")
    for name, data in prefectures.items():
        coord = data.get("map_coord", {})
        x = coord.get("x", 0)
        y = coord.get("y", 0)
        status = "✅" if x != 0 and y != 0 else "❌"
        comment = coord.get("comment", "")
        gp = data.get("grid_position", {})
        if gp:
            print(f"  {status} {name}: ({x}, {y}) [{gp.get('name', '?')}]")
        else:
            print(f"  {status} {name}: ({x}, {y})")

# ============================================================
# 阶段4: 一键全部流程
# ============================================================
def run_all():
    """一键运行全部流程"""
    print("\n" + "=" * 60)
    print("大地图分片标定 - 完整流程")
    print("=" * 60)
    print()
    print("⚠️  请确保:")
    print("  1. 模拟器已打开江南百景图")
    print("  2. 已进入大地图界面（点击左下角红色印章→大地图）")
    print("  3. 大地图已加载完成")
    print()
    
    mode = input("扫描模式 (3=3x3网格[默认], 4=4x4, 2=2x2): ").strip()
    try:
        n = int(mode) if mode else 3
    except ValueError:
        n = 3
    
    print(f"\n使用 {n}x{n} 网格扫描\n")
    
    # 扫描
    scan_map_grid(rows=n, cols=n)
    
    # 检测
    print("\n" + "=" * 60)
    print("自动进入检测阶段...")
    print("=" * 60)
    detect_all_regions()
    
    # 映射
    print("\n" + "=" * 60)
    print("自动进入映射阶段...")
    print("=" * 60)
    map_regions_to_prefectures()

# ============================================================
# 主入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="大地图分片探索工具")
    parser.add_argument("action", nargs="?", default="scan",
                        choices=["scan", "detect", "map", "all", "list", "show"],
                        help="操作: scan(扫描), detect(检测), map(映射), all(全部), list(列表), show(显示)")
    parser.add_argument("--pos", "-p", type=str, help="指定位置名称")
    parser.add_argument("--rows", "-r", type=int, default=3, help="网格行数")
    parser.add_argument("--cols", "-c", type=int, default=3, help="网格列数")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过确认提示")
    
    args = parser.parse_args()
    
    if args.action == "scan":
        scan_map_grid(rows=args.rows, cols=args.cols, skip_confirm=args.yes)
    elif args.action == "detect":
        detect_all_regions()
    elif args.action == "map":
        map_regions_to_prefectures()
    elif args.action == "all":
        run_all()
    elif args.action == "list":
        grid_data = load_grid_data()
        regions_by_pos = grid_data.get("regions_by_position", {})
        if args.pos:
            _list_regions(args.pos, regions_by_pos)
        else:
            print("可用位置:")
            for pos_name in regions_by_pos:
                total = len(regions_by_pos[pos_name]["regions"])
                print(f"  {pos_name}: {total} 个区域")
    elif args.action == "show":
        config = load_config()
        _show_all_prefectures(config)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
