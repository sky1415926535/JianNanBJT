#!/usr/bin/env python3
"""
批量映射工具 — 一次性将区域编号映射到府名
用法: python batch_map.py "白雪镇=r1_c0 42" "应天府=r0_c1 15" ...
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
GRID_DATA_PATH = BASE_DIR / "screenshots" / "map_grid" / "grid_data.json"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("使用方法: python batch_map.py \"府名=位置 编号\" ...")
        print()
        print("示例:")
        print('  python batch_map.py "白雪镇=r1_c0 42" "应天府=r0_c1 15"')
        print()
        print("详细步骤:")
        print("  1. 打开标注图片: screenshots/map_grid/r*_c*_annotated.png")
        print("  2. 找到每个府名对应的绿色/黄色边框编号")
        print("  3. 按格式输入: 府名=位置名 区域编号")
        print()
        print("可用位置: r0_c0, r0_c1, r0_c2, r1_c0, r1_c1, r1_c2, r2_c0, r2_c1, r2_c2")
        print("待标定府: 白雪镇, 应天府, 苏州府, 松江府, 徽州府, 扬州府")
        return

    config = load_json(CONFIG_PATH)
    grid_data = load_json(GRID_DATA_PATH)
    regions_by_pos = grid_data.get("regions_by_position", {})
    prefectures = config["prefecture"]["prefectures"]

    mapped = 0
    errors = 0

    for arg in sys.argv[1:]:
        try:
            prefecture_name, region_spec = arg.split("=", 1)
            position_name, region_id = region_spec.rsplit(" ", 1)
            region_id = int(region_id)
        except (ValueError, TypeError):
            print(f"❌ 格式错误: {arg}")
            errors += 1
            continue

        if prefecture_name not in prefectures:
            print(f"❌ 未知府名: {prefecture_name}")
            errors += 1
            continue

        if position_name not in regions_by_pos:
            print(f"❌ 未知位置: {position_name}")
            print(f"   可用: {', '.join(regions_by_pos.keys())}")
            errors += 1
            continue

        regions = regions_by_pos[position_name].get("regions", [])
        if region_id < 0 or region_id >= len(regions):
            print(f"❌ 区域编号 {region_id} 超出范围 (0-{len(regions)-1})")
            errors += 1
            continue

        region = regions[region_id]
        x = region["center_x"]
        y = region["center_y"]

        scroll_x = regions_by_pos[position_name]["scroll_x"]
        scroll_y = regions_by_pos[position_name]["scroll_y"]

        prefectures[prefecture_name]["map_coord"] = {
            "x": x,
            "y": y,
            "comment": f"大地图坐标【已标定】- {position_name}[{region_id}] 偏移({scroll_x},{scroll_y})"
        }

        # 同时保存网格位置信息
        prefectures[prefecture_name]["grid_position"] = {
            "name": position_name,
            "region_id": region_id,
            "scroll_x": scroll_x,
            "scroll_y": scroll_y
        }

        print(f"✅ {prefecture_name} → {position_name}[{region_id}] "
              f"中心({x},{y}) 偏移({scroll_x},{scroll_y})")
        mapped += 1

    if mapped > 0:
        save_json(CONFIG_PATH, config)
        print(f"\n💾 已保存 {mapped} 个府的坐标到 config.json")

    if errors > 0:
        print(f"⚠️  {errors} 个错误")

    # 显示剩余未标定的府
    remaining = []
    for name, data in prefectures.items():
        coord = data.get("map_coord", {})
        if coord.get("x", 0) == 0 and coord.get("y", 0) == 0:
            remaining.append(name)

    if remaining:
        print(f"\n📋 剩余待标定: {', '.join(remaining)}")
    else:
        print("\n✅ 所有府坐标已配置完成！")


if __name__ == "__main__":
    main()
