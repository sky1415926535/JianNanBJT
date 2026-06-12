#!/usr/bin/env python3
"""
使用 rapidocr 直接对网格截图做 OCR，自动标定府名坐标
用法: python rapid_ocr_calibrate.py
"""

import json
import sys
import time
import numpy as np
from pathlib import Path
import cv2

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
GRID_DIR = BASE_DIR / "screenshots" / "map_grid"
GRID_DATA_PATH = GRID_DIR / "grid_data.json"

PREFECTURE_NAMES = ["白雪镇", "应天府", "苏州府", "杭州府", "松江府", "徽州府", "扬州府", "绍兴府"]

# 延迟加载
_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        from rapidocr import RapidOCR
        print("  📥 加载 RapidOCR 模型（首次约 10s）...")
        # RapidOCR() 使用默认模型，自动下载
        _ocr = RapidOCR()
        print("  ✓ 模型加载完成")
    return _ocr


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def iou(box1, box2):
    """计算两个bbox的IoU"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area1 = (box1[2]-box1[0]) * (box1[3]-box1[1])
    area2 = (box2[2]-box2[0]) * (box2[3]-box2[1])
    return inter / (area1 + area2 - inter)


def match_prefecture(text):
    """模糊匹配府名"""
    text = text.strip().replace(" ", "").replace("　", "")
    for name in PREFECTURE_NAMES:
        # 完全匹配
        if name in text:
            return name
        # 模糊匹配（去掉"府"字）
        short = name.replace("府", "")
        if short in text:
            return name
    return None


def run_ocr_calibration():
    print("=" * 60)
    print("RapidOCR 自动标定府名位置")
    print("=" * 60)
    print()

    config = load_json(CONFIG_PATH)
    grid_data = load_json(GRID_DATA_PATH)
    prefectures = config["prefecture"]["prefectures"]

    # 找出未标定的府
    uncalibrated = {}
    for name, data in prefectures.items():
        coord = data.get("map_coord", {})
        if coord.get("x", 0) == 0 and coord.get("y", 0) == 0:
            uncalibrated[name] = data

    if not uncalibrated:
        print("✅ 所有府的坐标已配置完成！")
        return

    print(f"待标定府: {len(uncalibrated)} 个")
    print(f"   {', '.join(uncalibrated.keys())}")
    print()
    print("开始 OCR 识别...")
    print()

    ocr = get_ocr()
    found = {}  # 府名 -> {position, center_x, center_y, scroll_x, scroll_y, text}

    for pos in grid_data["positions"]:
        pos_name = pos["name"]
        img_path = GRID_DIR / f"{pos_name}.png"

        if not img_path.exists():
            print(f"  ⚠️  跳过 {pos_name}: 截图不存在")
            continue

        print(f"  🔍 OCR 识别 {pos_name}.png ...")

        try:
            result = ocr(str(img_path))
        except Exception as e:
            print(f"  ❌ OCR 失败: {e}")
            continue

        # result 是 RapidOCROutput 对象
        det_boxes = result.boxes
        det_texts = result.txts
        det_scores = result.scores
        if det_boxes is None or len(det_boxes) == 0:
            print(f"    未检测到文本")
            continue

        print(f"    检测到 {len(det_texts)} 段文本")

        for box, text, score in zip(det_boxes, det_texts, det_scores):
            if score < 0.5:
                continue

            matched_name = match_prefecture(text)
            if matched_name and matched_name not in found:
                # box 格式: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                box = np.array(box, dtype=np.int32)
                cx = int(box[:, 0].mean())
                cy = int(box[:, 1].mean())

                found[matched_name] = {
                    "name": matched_name,
                    "position": pos_name,
                    "center_x": cx,
                    "center_y": cy,
                    "scroll_x": pos["scroll_x"],
                    "scroll_y": pos["scroll_y"],
                    "text": text,
                    "score": round(score, 3),
                }
                print(f"    ✅ 找到 {matched_name}: '{text}' @ ({cx},{cy}) 置信度={score:.2f}")

        # 所有府都找到就提前退出
        if all(n in found for n in uncalibrated):
            break

    # 输出结果
    print()
    print("=" * 60)
    print(f"识别结果: 找到 {len(found)}/{len(uncalibrated)} 个府")
    print("=" * 60)
    print()

    if not found:
        print("❌ 未识别到任何府名")
        print()
        print("可能原因:")
        print("  1. 截图质量不佳（尝试重新截图）")
        print("  2. 字体特殊导致 OCR 无法识别")
        print("  3. 府名不在当前网格范围内")
        print()
        print("建议: 使用手动标定 python map_explorer.py map")
        return

    for name, info in found.items():
        print(f"  {name}:")
        print(f"    位置:  {info['position']}")
        print(f"    坐标:  ({info['center_x']}, {info['center_y']})")
        print(f"    偏移:  ({info['scroll_x']}, {info['scroll_y']})")
        print(f"    识别:  '{info['text']}' (置信度 {info['score']})")
        print()

    # 确认保存
    print("=" * 60)
    response = input("是否保存以上坐标到 config.json? (y/n): ").strip().lower()
    print()

    if response == "y":
        for name, info in found.items():
            prefectures[name]["map_coord"] = {
                "x": info["center_x"],
                "y": info["center_y"],
                "comment": f"大地图坐标【OCR标定】- {info['position']} 偏移({info['scroll_x']},{info['scroll_y']}) 识别:'{info['text']}'"
            }
            prefectures[name]["grid_position"] = {
                "name": info["position"],
                "scroll_x": info["scroll_x"],
                "scroll_y": info["scroll_y"],
            }

        save_json(CONFIG_PATH, config)
        print(f"💾 已保存 {len(found)} 个府的坐标到 config.json")
    else:
        print("⏭️  已取消保存")

    remaining = [n for n in uncalibrated if n not in found]
    if remaining:
        print()
        print(f"📋 剩余待标定: {', '.join(remaining)}")
        print(f"  手动标定: python map_explorer.py map")


if __name__ == "__main__":
    run_ocr_calibration()
