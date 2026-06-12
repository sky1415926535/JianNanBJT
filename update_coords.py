#!/usr/bin/env python3
"""
交互式坐标更新工具
使用方法：运行后按提示输入每个府对应的区域编号
"""

import json
from pathlib import Path

def main():
    # 加载区域坐标
    with open("screenshots/regions.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    regions = data["regions"]
    
    # 加载配置
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    prefectures = config["prefecture"]["prefectures"]
    
    print("=" * 60)
    print("江南百景图 - 坐标更新工具")
    print("=" * 60)
    print()
    print("请查看 screenshots/bigmap_regions.png")
    print("找到每个府名所在的区域编号，然后输入编号")
    print()
    
    for name in prefectures:
        coord = prefectures[name].get("map_coord", {})
        if coord.get("x", 0) != 0 or coord.get("y", 0) != 0:
            print(f"✅ {name} 已配置 ({coord["x"]}, {coord["y"]})")
            continue
        
        print(f"【{name}】")
        print(f"  请查看图片，找到 {name} 对应的区域编号")
        
        try:
            region_id = input(f"  输入区域编号（或按Enter跳过）: ").strip()
            if not region_id:
                print(f"  ⏭️  跳过 {name}")
                continue
            
            rid = int(region_id)
            region = regions[rid]
            x, y = region["center"]
            
            prefectures[name]["map_coord"]["x"] = x
            prefectures[name]["map_coord"]["y"] = y
            prefectures[name]["map_coord"]["comment"] = "大地图坐标【已标定】- MSER自动检测"
            
            print(f"  ✅ {name} 坐标已保存: ({x}, {y})")
        except (ValueError, IndexError) as e:
            print(f"  ❌ 错误: {e}")
        
        print()
    
    # 保存配置
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print("✅ 配置已保存到 config.json")

if __name__ == "__main__":
    main()
