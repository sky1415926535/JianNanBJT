#!/usr/bin/env python3
"""
生成区域匹配指南 - 帮助用户找到每个府对应的区域编号
根据府名的特征（2-3个汉字，特定位置）筛选可能的区域
"""

import json
from pathlib import Path

def load_regions():
    """加载区域数据"""
    with open('screenshots/regions.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def filter_text_like_regions(regions):
    """
    筛选类似文字的区域
    府名特征：
    - 宽度：60-300像素（2-6个汉字）
    - 高度：30-80像素（汉字高度）
    - 面积：2000-15000像素
    """
    filtered = []
    for region in regions:
        bbox = region['bbox']
        w, h = bbox[2], bbox[3]
        area = region['area']
        
        # 过滤条件：类似文字的大小
        if (60 <= w <= 300 and 
            30 <= h <= 80 and 
            2000 <= area <= 15000):
            filtered.append(region)
    
    return filtered

def main():
    # 加载区域
    data = load_regions()
    regions = data['regions']
    
    print("=" * 70)
    print("江南百景图 - 府名区域匹配指南")
    print("=" * 70)
    print()
    
    # 筛选文字区域
    text_regions = filter_text_like_regions(regions)
    
    print(f"总区域数: {len(regions)}")
    print(f"筛选后文字区域数: {len(text_regions)}")
    print()
    
    # 按Y坐标排序（从上到下）
    text_regions.sort(key=lambda r: r['center'][1])
    
    # 生成匹配指南
    print("=" * 70)
    print("可能的府名区域（按从上到下排序）")
    print("=" * 70)
    print()
    print(f"{'编号':<8} {'中心坐标':<20} {'宽x高':<15} {'面积':<10} {'位置':<15}")
    print("-" * 70)
    
    for region in text_regions:
        rid = region['id']
        center = region['center']
        bbox = region['bbox']
        w, h = bbox[2], bbox[3]
        area = region['area']
        
        # 判断位置（上/中/下，左/中/右）
        x, y = center
        pos_x = '左' if x < 640 else ('中' if x < 1280 else '右')
        pos_y = '上' if y < 360 else ('中' if y < 720 else '下')
        position = f"{pos_y}{pos_x}"
        
        print(f"[{rid:03d}]    ({center[0]:>4}, {center[1]:>4})    {w:>4}x{h:<4}    {area:>6}    {position:<15}")
    
    print()
    print("=" * 70)
    print("匹配步骤：")
    print("=" * 70)
    print()
    print("1. 打开图片: screenshots/bigmap_regions.png")
    print("2. 在图片中找到所有府名的位置（应天府、苏州府、杭州府等）")
    print("3. 记录每个府名旁边的编号（如 [042]）")
    print("4. 根据上表找到该编号对应的坐标")
    print("5. 运行以下命令更新配置：")
    print()
    print("   python -c \"import json; \\")
    print("   f=open('config.json','r'); c=json.load(f); \\")
    print("   c['prefecture']['prefectures']['府名']['map_coord']={'x':X,'y':Y,'comment':'已标定'}; \\")
    print("   open('config.json','w').write(json.dumps(c, ensure_ascii=False, indent=2))\"")
    print()
    print("   或手动编辑 config.json")
    print()
    
    # 生成便于复制的坐标列表
    print("=" * 70)
    print("坐标速查表（便于复制）")
    print("=" * 70)
    print()
    
    for region in text_regions:
        rid = region['id']
        center = region['center']
        print(f"区域 [{rid:03d}]: {{'x': {center[0]}, 'y': {center[1]}}}")
    
    print()
    print("=" * 70)
    print("已知府的坐标（已标定）：")
    print("=" * 70)
    print()
    print("杭州府: (789, 352)")
    print("绍兴府: (940, 687)")
    print()
    
    # 保存筛选后的区域到文件
    output_path = Path('screenshots/text_regions.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_filtered': len(text_regions),
            'regions': text_regions
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 筛选后的区域已保存到: {output_path}")
    print()

if __name__ == '__main__':
    main()
