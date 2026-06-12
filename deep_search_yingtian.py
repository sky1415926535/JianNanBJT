#!/usr/bin/env python3
"""低阈值 OCR 搜索：查找可能被漏掉的 应天府"""
from rapidocr import RapidOCR
import json
from pathlib import Path

GRID_DIR = Path(__file__).parent / "screenshots" / "map_grid"
grid_data = json.load(open(GRID_DIR / "grid_data.json"))
ocr = RapidOCR()

# 府名关键词搜索
TARGETS = ["应天", "天府", "应", "天", "府"]

# 只搜索之前的空白区域（r0_c3, r0_c4, r1_c3, r1_c4, r2_c3, r2_c4, r3_*, r4_*）
new_positions = [
    p for p in grid_data["positions"]
    if p["row"] >= 3 or p["col"] >= 3  # 新扩展区域
]

print("=" * 60)
print(f"在 5×5 网格新扩展区域 ({len(new_positions)}个) 搜索应天府")
print("=" * 60)
print(f"关键词: {TARGETS}")
print()

for pos in new_positions:
    img_path = GRID_DIR / f"{pos['name']}.png"
    if not img_path.exists():
        continue

    result = ocr(str(img_path))
    txts = result.txts
    score_list = result.scores
    if not txts:
        continue

    hits = []
    for txt, confidence in zip(txts, score_list):
        if confidence < 0.3:  # 极低阈值
            continue
        if any(kw in txt for kw in TARGETS):
            hits.append(f"'{txt}'({confidence:.2f})")

    if hits:
        offset = f"偏移({pos['scroll_x']},{pos['scroll_y']})"
        print(f"[{pos['name']}] {offset}: {', '.join(hits)}")

# 也搜索所有位置中任意含 "X府" 格式但不匹配已知府名的文本
print(f"\n--- 所有含'府'的文本 (任意位置) ---")
known = {"扬州府", "苏州府", "杭州府", "松江府", "徽州府", "绍兴府", "宁波府"}
all_fu = {}
for pos in grid_data["positions"]:
    img_path = GRID_DIR / f"{pos['name']}.png"
    if not img_path.exists():
        continue
    result = ocr(str(img_path))
    txts = result.txts
    score_list = result.scores
    if not txts:
        continue
    for txt, confidence in zip(txts, score_list):
        if confidence < 0.3:
            continue
        if "府" in txt and txt not in known:
            key = txt
            if key not in all_fu:
                all_fu[key] = []
            all_fu[key].append((pos["name"], confidence))

if all_fu:
    for txt, locs in sorted(all_fu.items()):
        best = max(locs, key=lambda x: x[1])
        print(f"  '{txt}' ({best[1]:.2f}) @ {best[0]}")
else:
    print("  (无新的含'府'文本)")

# 3. 搜索所有含 "应" 的文本
print(f"\n--- 所有含'应'的文本 (任意位置, 置信度>=0.2) ---")
found_ying = False
for pos in grid_data["positions"]:
    img_path = GRID_DIR / f"{pos['name']}.png"
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
            print(f"  [{pos['name']}] '{txt}' ({confidence:.2f})")
            found_ying = True
if not found_ying:
    print("  (未找到含'应'的文本)")
