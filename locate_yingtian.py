#!/usr/bin/env python3
"""精确标定应天府坐标（从 center_default 截图中）"""
from rapidocr import RapidOCR
import numpy as np
from pathlib import Path

IMG = Path(__file__).parent / "screenshots" / "map_full" / "center_default.png"
ocr = RapidOCR()

result = ocr(str(IMG))
boxes = result.boxes
txts = result.txts
score_list = result.scores

print("=" * 60)
print("在 center_default.png 中搜索 '应天府'")
print("=" * 60)

target = None
for box, txt, confidence in zip(boxes, txts, score_list):
    if "应天" in txt or txt == "应天府":
        pts = np.array(box, dtype=int)
        x1, y1 = int(pts[:, 0].min()), int(pts[:, 1].min())
        x2, y2 = int(pts[:, 0].max()), int(pts[:, 1].max())
        cx, cy = int(pts[:, 0].mean()), int(pts[:, 1].mean())
        print(f"\n✅ 找到: '{txt}' (置信度 {confidence:.2f})")
        print(f"  边界框: ({x1},{y1}) ~ ({x2},{y2})")
        print(f"  中心点: ({cx}, {cy})")
        print(f"  尺寸: {x2-x1}x{y2-y1}")
        target = (cx, cy)
        break

if target is None:
    print("\n❌ 未在 center_default.png 中找到 '应天府'")
    print("所有识别文本:")
    for txt, confidence in zip(txts, score_list):
        if confidence >= 0.3 and "府" in txt:
            print(f"  ({confidence:.2f}) {txt}")
else:
    cx, cy = target
    print(f"\n{'=' * 60}")
    print(f"应天府 屏幕坐标: ({cx}, {cy})")
    print(f"{'=' * 60}")
    print(f"\n可直接写入 config.json:")
    print(f"""
  "应天府": {{
    "map_coord": {{
      "x": {cx},
      "y": {cy},
      "comment": "大地图坐标【OCR标定】- center_default 默认视图"
    }}
  }}
""")
