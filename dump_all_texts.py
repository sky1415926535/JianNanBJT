#!/usr/bin/env python3
"""导出所有 OCR 识别到的文本及位置"""
from rapidocr import RapidOCR
import json
from pathlib import Path

GRID_DIR = Path(__file__).parent / "screenshots" / "map_grid"

grid_data = json.load(open(GRID_DIR / "grid_data.json"))
ocr = RapidOCR()

all_texts = set()
print("=== 按位置分组的识别结果 ===")
for pos in grid_data["positions"]:
    img_path = GRID_DIR / f"{pos['name']}.png"
    if not img_path.exists():
        continue
    result = ocr(str(img_path))
    txts = result.txts
    score_list = result.scores
    if not txts:
        continue

    items = []
    for txt, confidence in zip(txts, score_list):
        if confidence >= 0.5 and len(txt) >= 2:
            items.append(f"'{txt}'({confidence:.2f})")
            all_texts.add(txt)

    if items:
        offset = f"偏移({pos['scroll_x']},{pos['scroll_y']})"
        print(f"\n【{pos['name']}】 {offset}")
        print(f"  {', '.join(items)}")

print(f"\n\n=== 汇总 (置信度>=0.5, 长度>=2) ===")
for t in sorted(all_texts):
    print(f"  {t}")
print(f"\n总计: {len(all_texts)} 个不同文本")
