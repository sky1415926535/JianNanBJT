#!/usr/bin/env python3
"""OCR 四方向扫描结果，搜索应天府"""
from rapidocr import RapidOCR
from pathlib import Path

SCAN_DIR = Path(__file__).parent / "screenshots" / "map_full"
ocr = RapidOCR()

TARGET = "应天府"
KEYWORDS = ["应", "天", "应天"]

print("=" * 60)
print("四方向扫描 OCR 结果")
print("=" * 60)

for name in ["center_default", "up_1", "down_1", "left_1", "right_1"]:
    img_path = SCAN_DIR / f"{name}.png"
    if not img_path.exists():
        print(f"\n[{name}] 文件不存在")
        continue

    result = ocr(str(img_path))
    txts = result.txts
    score_list = result.scores
    if not txts:
        print(f"\n[{name}] 未识别到文本")
        continue

    print(f"\n[{name}] 识别结果:")
    found = False
    for txt, confidence in zip(txts, score_list):
        if confidence < 0.3:
            continue
        mark = " 🎯" if any(kw in txt for kw in KEYWORDS) else ""
        if mark or "府" in txt:
            print(f"  ({confidence:.2f}) {txt}{mark}")
            found = True
    if not found:
        print("  (无相关文本)")

# 专门搜索含"应"的文本
print(f"\n{'=' * 60}")
print("专门搜索含'应'关键字的文本 (置信度>=0.2)")
print("=" * 60)

for name in ["center_default", "up_1", "down_1", "left_1", "right_1"]:
    img_path = SCAN_DIR / f"{name}.png"
    if not img_path.exists():
        continue
    result = ocr(str(img_path))
    txts = result.txts
    score_list = result.scores
    if not txts:
        continue
    for txt, confidence in zip(txts, score_list):
        if confidence < 0.2:
            continue
        if "应" in txt:
            print(f"  [{name}] ({confidence:.2f}) {txt}")
            break
    else:
        continue
    break
else:
    print("  未找到含'应'的文本")
