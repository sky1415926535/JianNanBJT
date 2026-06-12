#!/usr/bin/env python3
"""分析大地图截图，用 PaddleOCR 识别州府名称"""
import sys
import cv2
import numpy as np

sys.path.insert(0, 'E:/AI-workspace/JianNanBJT')
from common.ocr import OCREngine

IMG_PATH = 'E:/AI-workspace/JianNanBJT/screenshots/bigmap_calibrate.png'

# 检查游戏状态
img = cv2.imread(IMG_PATH)
if img is None:
    print('ERROR: 无法读取截图')
    sys.exit(1)

h, w = img.shape[:2]
print(f'截图尺寸: {w}x{h}')

# 左下角红色比例
lb = img[int(h*0.65):h, 0:int(w*0.13)]
r = lb[:,:,2].astype(np.float32)
g = lb[:,:,1].astype(np.float32)
b = lb[:,:,0].astype(np.float32)
red_mask = (r > 120) & (r > g*1.2) & (r > b*1.2)
red_ratio = np.sum(red_mask) / red_mask.size
print(f'左下角红色比例: {red_ratio:.3f}')
if red_ratio < 0.08:
    print('✅ 确认：当前在大地图界面')
elif red_ratio > 0.20:
    print('⚠️  警告：当前在城镇视图（州府印可见）')
else:
    print('? 不确定当前界面')

# PaddleOCR 识别
print('\n正在初始化 PaddleOCR...')
ocr = OCREngine()
print(f'OCR 引擎: {ocr.engine_name}')

if ocr.engine_name == 'mser_only':
    print('⚠️  PaddleOCR 初始化失败，仅 MSER 可用（无法识别文字）')
    print('请检查 PaddleOCR 安装: pip show paddleocr')
    sys.exit(1)

print('正在识别文字...')
results = ocr.recognize(img)
print(f'识别到 {len(results)} 个文字区域')

# 过滤州府名称
print('\n含"府"字的文字:')
for r in results:
    text = r.get('text', '')
    conf = r.get('conf', -1)
    cx, cy = r.get('center', (0, 0))
    if '府' in text:
        print(f'  ✅ {text:>8}  conf={conf:.2f}  center=({cx:>4}, {cy:>4})')

# 保存标注图
annotated = img.copy()
for r in results:
    text = r.get('text', '')
    if '府' in text:
        bbox = r.get('bbox', (0,0,0,0))
        x, y, bw, bh = bbox
        cv2.rectangle(annotated, (x, y), (x+bw, y+bh), (0, 255, 0), 2)
        cx, cy = r.get('center', (x+bw//2, y+bh//2))
        cv2.putText(annotated, text, (cx-30, cy-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

out_path = 'E:/AI-workspace/JianNanBJT/screenshots/bigmap_ocr_result.png'
cv2.imwrite(out_path, annotated)
print(f'\n标注图已保存: {out_path}')
