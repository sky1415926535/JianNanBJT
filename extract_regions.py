#!/usr/bin/env python3
"""
提取大地图MSER检测区域坐标
运行后生成 regions.json，包含所有检测到的区域坐标
用户可以查看 annotated 图片，然后告诉我哪个编号对应哪个府
"""

import cv2
import json
import numpy as np
from pathlib import Path

def load_image(path):
    """加载图片"""
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {path}")
    return img

def detect_mser_regions(img, min_area=1500, max_area=50000):
    """使用MSER检测文字区域"""
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 创建MSER检测器
    mser = cv2.MSER_create(
        delta=5,
        min_area=min_area,
        max_area=max_area,
        max_variation=0.25,
        min_diversity=0.2
    )
    
    # 检测MSER区域
    regions, bboxes = mser.detectRegions(gray)
    
    # 处理检测结果
    results = []
    for i, bbox in enumerate(bboxes):
        x, y, w, h = bbox
        center_x = x + w // 2
        center_y = y + h // 2
        
        results.append({
            'id': i,
            'bbox': [int(x), int(y), int(w), int(h)],
            'center': [int(center_x), int(center_y)],
            'area': int(w * h)
        })
    
    # 按面积排序（大的在前）
    results.sort(key=lambda x: x['area'], reverse=True)
    
    # 重新编号
    for i, r in enumerate(results):
        r['id'] = i
    
    return results

def draw_annotated_image(img, regions, output_path):
    """绘制标注图像"""
    annotated = img.copy()
    
    for region in regions:
        x, y, w, h = region['bbox']
        center_x, center_y = region['center']
        
        # 绘制边界框
        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # 绘制编号
        label = f"[{region['id']:03d}]"
        cv2.putText(annotated, label, (x, y-5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        
        # 绘制中心点
        cv2.circle(annotated, (center_x, center_y), 3, (0, 0, 255), -1)
    
    cv2.imwrite(str(output_path), annotated)
    print(f"✅ 标注图像已保存: {output_path}")

def main():
    # 路径配置
    screenshot_dir = Path('screenshots')
    input_image = screenshot_dir / 'bigmap_calibrate.png'
    output_json = screenshot_dir / 'regions.json'
    output_image = screenshot_dir / 'bigmap_regions.png'
    
    if not input_image.exists():
        print(f"❌ 未找到输入图片: {input_image}")
        print("请先运行 adb shell screencap 获取大地图截图")
        return
    
    print("=" * 60)
    print("MSER 区域检测")
    print("=" * 60)
    print()
    
    # 加载图片
    print(f"正在加载图片: {input_image}")
    img = load_image(input_image)
    print(f"图片尺寸: {img.shape[1]}x{img.shape[0]}")
    print()
    
    # 检测区域
    print("正在检测MSER区域...")
    regions = detect_mser_regions(img)
    print(f"✅ 检测到 {len(regions)} 个区域")
    print()
    
    # 保存区域坐标到JSON
    print(f"正在保存区域坐标到: {output_json}")
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump({
            'total_regions': len(regions),
            'image_size': [img.shape[1], img.shape[0]],
            'regions': regions
        }, f, ensure_ascii=False, indent=2)
    print("✅ 坐标已保存")
    print()
    
    # 生成标注图像
    print(f"正在生成标注图像: {output_image}")
    draw_annotated_image(img, regions, output_image)
    print()
    
    # 输出区域列表（前50个最大的区域）
    print("=" * 60)
    print("区域坐标列表（按面积排序，显示前50个）")
    print("=" * 60)
    print()
    print(f"{'编号':<8} {'中心坐标':<15} {'边框':<20} {'面积':<10}")
    print("-" * 60)
    
    for region in regions[:50]:
        center = region['center']
        bbox = region['bbox']
        area = region['area']
        print(f"[{region['id']:03d}]    ({center[0]:>4}, {center[1]:>4})    [{bbox[0]:>4}, {bbox[1]:>4}, {bbox[2]:>4}, {bbox[3]:>4}]    {area:>6}")
    
    print()
    print("=" * 60)
    print("下一步操作：")
    print("=" * 60)
    print()
    print("1. 打开标注图像: screenshots/bigmap_regions.png")
    print("2. 找到每个府名所在的区域编号")
    print("3. 运行以下命令输入坐标：")
    print()
    print("   python update_coords.py")
    print()
    print("或者手动编辑 config.json，在对应的府下填写：")
    print('  "map_coord": {"x": 中心X, "y": 中心Y}')
    print()
    
    # 生成更新脚本
    generate_update_script(regions)

def generate_update_script(regions):
    """生成坐标更新脚本"""
    script_path = Path('update_coords.py')
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('#!/usr/bin/env python3\n')
        f.write('"""\n')
        f.write('交互式坐标更新工具\n')
        f.write('使用方法：运行后按提示输入每个府对应的区域编号\n')
        f.write('"""\n\n')
        f.write('import json\n')
        f.write('from pathlib import Path\n\n')
        f.write('def main():\n')
        f.write('    # 加载区域坐标\n')
        f.write('    with open("screenshots/regions.json", "r", encoding="utf-8") as f:\n')
        f.write('        data = json.load(f)\n')
        f.write('    regions = data["regions"]\n')
        f.write('    \n')
        f.write('    # 加载配置\n')
        f.write('    with open("config.json", "r", encoding="utf-8") as f:\n')
        f.write('        config = json.load(f)\n')
        f.write('    \n')
        f.write('    prefectures = config["prefecture"]["prefectures"]\n')
        f.write('    \n')
        f.write('    print("=" * 60)\n')
        f.write('    print("江南百景图 - 坐标更新工具")\n')
        f.write('    print("=" * 60)\n')
        f.write('    print()\n')
        f.write('    print("请查看 screenshots/bigmap_regions.png")\n')
        f.write('    print("找到每个府名所在的区域编号，然后输入编号")\n')
        f.write('    print()\n')
        f.write('    \n')
        f.write('    for name in prefectures:\n')
        f.write('        coord = prefectures[name].get("map_coord", {})\n')
        f.write('        if coord.get("x", 0) != 0 or coord.get("y", 0) != 0:\n')
        f.write('            print(f"✅ {name} 已配置 ({coord["x"]}, {coord["y"]})")\n')
        f.write('            continue\n')
        f.write('        \n')
        f.write('        print(f"【{name}】")\n')
        f.write('        print(f"  请查看图片，找到 {name} 对应的区域编号")\n')
        f.write('        \n')
        f.write('        try:\n')
        f.write('            region_id = input(f"  输入区域编号（或按Enter跳过）: ").strip()\n')
        f.write('            if not region_id:\n')
        f.write('                print(f"  ⏭️  跳过 {name}")\n')
        f.write('                continue\n')
        f.write('            \n')
        f.write('            rid = int(region_id)\n')
        f.write('            region = regions[rid]\n')
        f.write('            x, y = region["center"]\n')
        f.write('            \n')
        f.write('            prefectures[name]["map_coord"]["x"] = x\n')
        f.write('            prefectures[name]["map_coord"]["y"] = y\n')
        f.write('            prefectures[name]["map_coord"]["comment"] = "大地图坐标【已标定】- MSER自动检测"\n')
        f.write('            \n')
        f.write('            print(f"  ✅ {name} 坐标已保存: ({x}, {y})")\n')
        f.write('        except (ValueError, IndexError) as e:\n')
        f.write('            print(f"  ❌ 错误: {e}")\n')
        f.write('        \n')
        f.write('        print()\n')
        f.write('    \n')
        f.write('    # 保存配置\n')
        f.write('    with open("config.json", "w", encoding="utf-8") as f:\n')
        f.write('        json.dump(config, f, ensure_ascii=False, indent=2)\n')
        f.write('    \n')
        f.write('    print("✅ 配置已保存到 config.json")\n')
        f.write('\n')
        f.write('if __name__ == "__main__":\n')
        f.write('    main()\n')
    
    print(f"✅ 已生成坐标更新脚本: {script_path}")
    print(f"   运行: python {script_path}")

if __name__ == '__main__':
    main()
