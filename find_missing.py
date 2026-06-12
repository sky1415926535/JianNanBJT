#!/usr/bin/env python3
"""打印所有 OCR 识别结果，查找 白雪镇/应天府"""
from rapidocr import RapidOCR
import json, numpy as np
from pathlib import Path

GRID_DIR = Path(__file__).parent / "screenshots" / "map_grid"

grid_data = json.load(open(GRID_DIR / "grid_data.json"))
ocr = RapidOCR()

for pos in grid_data["positions"]:
    img_path = GRID_DIR / f"{pos['name']}.png"
    if not img_path.exists():
        continue
    result = ocr(str(img_path))
    boxes = result.boxes
    txts = result.txts
    scores = result.scores
    if boxes is None or (hasattr(boxes, '__len__') and len(boxes) == 0):
        continue
    found_interesting = False
    for box, txt, sc in zip(boxes, txts, scores):
        if sc < 0.4:
            continue
        pts = np.array(box, dtype=int)
        cx, cy = int(pts[:, 0].mean()), int(pts[:, 1].mean())
        # 标记包含关键字的
        keywords = ["应", "天", "白", "雪"]  # 只关注应天府/白雪镇
        mark = "⭐" if any(k in txt for k in keywords) else "  "
        if mark == "⭐":
            if not found_interesting:
                print(f"\n【{pos['name']}】 偏移({pos['scroll_x']},{pos['scroll_y']})")
                found_interesting = True
            print(f"  {mark} ({cx:4d},{cy:4d}) [{sc:.2f}] {txt}")
