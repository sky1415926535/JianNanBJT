#!/usr/bin/env python3
"""用 MSER 快速检测大地图文字区域并输出坐标（无需 GPU/模型下载）"""
import cv2
import numpy as np
import sys

sys.path.insert(0, 'E:/AI-workspace/JianNanBJT')
from common.ocr import OCREngine

IMG_PATH = 'E:/AI-workspace/JianNanBJT/screenshots/bigmap_calibrate.png'
img = cv2.imread(IMG_PATH)
if img is None:
    print('ERROR: 无法读取截图')
    sys.exit(1)

h, w = img.shape[:2]

# 强制 MSER-only 模式（快速，无需模型）
ocr = OCREngine(engine='mser_only')
results = ocr.recognize(img)
print(f'MSER 检测到 {len(results)} 个文字区域')
print(f'图片尺寸: {w}x{h}')
print()

# 按 Y 坐标排序
results.sort(key=lambda r: r['center'][1])

# 标注图
annotated = img.copy()

print(f"{'#':>3}  {'center_x':>6}  {'center_y':>6}  {'area':>6}  {'w':>4}  {'h':>4}")
print('-' * 45)
for i, r in enumerate(results):
    cx, cy = r['center']
    bx, by, bw, bh = r['bbox']
    area = bw * bh
    print(f'{i:>3}  {cx:>6}  {cy:>6}  {area:>6}  {bw:>4}  {bh:>4}')
    
    # 标注（暂时用序号）
    cv2.rectangle(annotated, (bx, by), (bx+bw, by+bh), (0, 255, 0), 2)
    cv2.putText(annotated, str(i), (bx, by-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

# 画网格辅助线
for x in range(0, w, 200):
    cv2.line(annotated, (x, 0), (x, h), (100, 100, 100), 1)
for y in range(0, h, 200):
    cv2.line(annotated, (0, y), (w, y), (100, 100, 100), 1)

out_path = 'E:/AI-workspace/JianNanBJT/screenshots/bigmap_mser_regions.png'
cv2.imwrite(out_path, annotated)
print(f'\n标注图已保存: {out_path}')
print('请查看标注图，找到州府名称对应的序号')
print('参考州府: 应天府、苏州府、杭州府、扬州府、徽州府、广州府、成都府、南京')
