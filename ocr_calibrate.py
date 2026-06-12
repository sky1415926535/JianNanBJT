#!/usr/bin/env python3
"""
OCR自动标定府名位置
使用 cnocr 识别标注图片中的府名，自动映射到 config.json
"""

import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
GRID_DIR = BASE_DIR / "screenshots" / "map_grid"
GRID_DATA_PATH = GRID_DIR / "grid_data.json"

# 所有府名列表
PREFECTURE_NAMES = ["白雪镇", "应天府", "苏州府", "杭州府", "松江府", "徽州府", "扬州府", "绍兴府"]

# 初始化 cnocr（延迟加载）
_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        from cnocr import CnOcr
        print("  📥 加载 CnOcr 模型（首次运行，请稍候）...")
        _ocr = CnOcr(
            det_model_name="db_resnet34",   # 文本检测模型
            rec_model_name="ch_PP-OCRv4",   # 中文识别模型
            det_db_thresh=0.3,
            det_db_box_thresh=0.5,
        )
        print("  ✓ 模型加载完成")
    return _ocr


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def crop_region(image, bbox):
    """根据bbox裁剪区域 (bbox格式: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]])"""
    pts = np.array(bbox, dtype=np.int32)
    x_min, y_min = pts[:, 0].min(), pts[:, 1].min()
    x_max, y_max = pts[:, 0].max(), pts[:, 1].max()
    return image[y_min:y_max, x_min:x_max]


def ocr_image(image_path):
    """对整张图片进行OCR，返回 (文本, bbox) 列表"""
    ocr = get_ocr()
    result = ocr.ocr(str(image_path))
    return result


def match_prefecture_name(text):
    """将OCR识别文本匹配到府名"""
    text = text.strip()
    for name in PREFECTURE_NAMES:
        if name in text or text in name:
            return name
    return None


def run_ocr_calibration():
    """主函数：OCR识别 + 自动标定"""
    print("=" * 60)
    print("OCR 自动标定府名位置 (cnocr)")
    print("=" * 60)
    print()

    config = load_json(CONFIG_PATH)
    grid_data = load_json(GRID_DATA_PATH)
    regions_by_pos = grid_data.get("regions_by_position", {})
    prefectures = config["prefecture"]["prefectures"]

    # 找出未标定的府
    uncalibrated = []
    for name, data in prefectures.items():
        coord = data.get("map_coord", {})
        if coord.get("x", 0) == 0 and coord.get("y", 0) == 0:
            uncalibrated.append(name)

    if not uncalibrated:
        print("✅ 所有府的坐标已配置完成！")
        return

    print(f"待标定府: {len(uncalibrated)} 个")
    print(f"   {', '.join(uncalibrated)}")
    print()
    print("开始 OCR 识别...")
    print()

    # 存储识别结果: {府名: (位置名, 区域编号, 中心坐标)}
    found = {}

    # 遍历所有网格位置
    for pos in grid_data["positions"]:
        pos_name = pos["name"]
        screenshot_path = GRID_DIR / f"{pos_name}.png"

        if not screenshot_path.exists():
            print(f"  ⚠️  跳过 {pos_name}: 截图不存在")
            continue

        print(f"  🔍 OCR 识别 {pos_name}.png ...")

        try:
            result = ocr_image(screenshot_path)
        except Exception as e:
            print(f"  ❌ OCR 失败: {e}")
            continue

        # result 格式: [[{"text": "...", "bbox": [...], "score": ...}, ...]]
        # 展平结果
        texts = []
        if isinstance(result, list):
            for page in result:
                if isinstance(page, list):
                    for line in page:
                        if isinstance(line, dict) and "text" in line:
                            texts.append(line)

        print(f"    检测到 {len(texts)} 段文本")

        # 匹配府名
        for line in texts:
            text = line.get("text", "")
            bbox = line.get("bbox", [])
            matched_name = match_prefecture_name(text)

            if matched_name and matched_name not in found:
                # 计算中心坐标
                pts = np.array(bbox, dtype=np.int32)
                cx = int(pts[:, 0].mean())
                cy = int(pts[:, 1].mean())

                found[matched_name] = {
                    "name": matched_name,
                    "position": pos_name,
                    "center_x": cx,
                    "center_y": cy,
                    "scroll_x": pos["scroll_x"],
                    "scroll_y": pos["scroll_y"],
                    "text": text,
                    "bbox": bbox,
                }
                print(f"    ✅ 找到 {matched_name}: '{text}' @ ({cx},{cy})")

        # 如果所有府都找到了，提前退出
        if all(name in found for name in uncalibrated):
            break

    print()
    print("=" * 60)
    print(f"识别结果: 找到 {len(found)}/{len(uncalibrated)} 个府")
    print("=" * 60)
    print()

    if not found:
        print("❌ 未识别到任何府名，请尝试：")
        print("  1. 检查截图质量")
        print("  2. 手动标定: python map_explorer.py map")
        return

    # 显示识别结果
    for name, info in found.items():
        print(f"  {name}:")
        print(f"    位置: {info['position']}")
        print(f"    坐标: ({info['center_x']}, {info['center_y']})")
        print(f"    偏移: ({info['scroll_x']}, {info['scroll_y']})")
        print(f"    识别文本: '{info['text']}'")
        print()

    # 确认并保存
    print("=" * 60)
    response = input("是否保存以上坐标到 config.json? (y/n): ").strip().lower()
    print()

    if response == "y":
        for name, info in found.items():
            prefectures[name]["map_coord"] = {
                "x": info["center_x"],
                "y": info["center_y"],
                "comment": f"大地图坐标【OCR标定】- {info['position']} 偏移({info['scroll_x']},{info['scroll_y']})"
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

    # 显示剩余未标定的府
    remaining = [n for n in uncalibrated if n not in found]
    if remaining:
        print()
        print(f"📋 剩余待标定: {', '.join(remaining)}")
        print(f"  手动标定: python map_explorer.py map")


def run_ocr_on_all():
    """对所有网格截图进行OCR，输出详细结果（不自动保存）"""
    print("=" * 60)
    print("OCR 识别所有网格截图")
    print("=" * 60)
    print()

    grid_data = load_json(GRID_DATA_PATH)

    for pos in grid_data["positions"]:
        pos_name = pos["name"]
        screenshot_path = GRID_DIR / f"{pos_name}.png"

        if not screenshot_path.exists():
            continue

        print(f"【{pos_name}】 ({screenshot_path.name})")
        print(f"  偏移量: ({pos['scroll_x']}, {pos['scroll_y']})")

        try:
            result = ocr_image(screenshot_path)
        except Exception as e:
            print(f"  ❌ OCR 失败: {e}")
            continue

        texts = []
        if isinstance(result, list):
            for page in result:
                if isinstance(page, list):
                    for line in page:
                        if isinstance(line, dict) and "text" in line:
                            texts.append(line)

        if not texts:
            print("  未检测到文本")
        else:
            for line in texts:
                text = line.get("text", "")
                bbox = line.get("bbox", [])
                pts = np.array(bbox, dtype=np.int32) if bbox else np.array([[0,0]])
                cx = int(pts[:, 0].mean()) if len(pts) > 0 else 0
                cy = int(pts[:, 1].mean()) if len(pts) > 0 else 0
                print(f"  [{cx:4d},{cy:4d}] '{text}'")

        print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "calibrate"

    if mode == "scan":
        run_ocr_on_all()
    else:
        run_ocr_calibration()
