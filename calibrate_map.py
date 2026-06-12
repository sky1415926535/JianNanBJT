#!/usr/bin/env python3
"""
用 MSER 文字区域检测 + 手动辅助，标定各州府地图坐标。

【离线模式】（默认，无需 OCR 模型）:
  1. 进入大地图
  2. 截图
  3. MSER 检测所有文字区域（common/ocr.py 的 MSER-only 模式）
  4. 生成标注图（绿色框），保存到大地图截图旁
  5. 在标注图上手动识别各州府名称，填入 config.json

【OCR 模式】（需要 PaddleOCR 模型已下载）:
  自动识别州府名称并输出坐标。

用法:
  python calibrate_map.py              # 离线 MSER 模式（推荐先跑这个）
  python calibrate_map.py --ocr        # OCR 模式（需要模型）
  python calibrate_map.py --help
"""
import sys
import os
import time
import argparse
import numpy as np
import cv2

sys.path.insert(0, r'E:\AI-workspace\JianNanBJT')
from common import ADB, load_config
from common.ocr import OCREngine, detect_engine

SCREENSHOT_DIR = r'E:\AI-workspace\JianNanBJT\screenshots'
BIGMAP_PATH = os.path.join(SCREENSHOT_DIR, 'bigmap_calibrate.png')
ANNOTATED_PATH = os.path.join(SCREENSHOT_DIR, 'bigmap_calibrate_annotated.png')

# ---- 大地图进入逻辑（复用 prefecture.py 的两步点击）----
def ensure_on_big_map(cfg):
    pref_cfg = cfg.get('prefecture', {})
    enter_btn = pref_cfg.get('big_map_enter_btn', {})
    menu_btn = pref_cfg.get('big_map_menu_btn', {})
    enter_x = enter_btn.get('x', 108)
    enter_y = enter_btn.get('y', 908)
    menu_x = menu_btn.get('x', 218)
    menu_y = menu_btn.get('y', 389)

    for attempt in range(3):
        img = ADB.screenshot()
        if img is not None and _is_on_big_map(img):
            print('  ✅ 已在大地图界面')
            return True
        print(f'  尝试第{attempt+1}次: 点击州府印 ({enter_x},{enter_y}) → 大地图按钮 ({menu_x},{menu_y})')
        ADB.tap(enter_x, enter_y)
        time.sleep(0.5)
        ADB.tap(menu_x, menu_y)
        time.sleep(3.0)
    else:
        print('  ⚠️ 未能确认进入大地图，继续尝试...')
    return True

def _is_on_big_map(img):
    h, w = img.shape[:2]
    lb = img[int(h*0.65):h, 0:int(w*0.13)]
    r = lb[:,:,2].astype(np.float32)
    g = lb[:,:,1].astype(np.float32)
    b = lb[:,:,0].astype(np.float32)
    red_mask = (r > 120) & (r > g*1.2) & (r > b*1.2)
    red_ratio = np.sum(red_mask) / red_mask.size
    return red_ratio < 0.08


def run_mser_mode(cfg):
    """离线 MSER 模式：检测文字区域，生成标注图。"""
    print('='*60)
    print('模式: MSER 离线标注（无需 OCR 模型）')
    print('='*60)

    # Step 1: 进入大地图
    print('\n[1/4] 确保进入大地图...')
    ensure_on_big_map(cfg)

    # Step 2: 截图
    print('\n[2/4] 截取大地图画面...')
    img = ADB.screenshot(save_path=BIGMAP_PATH)
    if img is None:
        print('  ❌ 截图失败')
        sys.exit(1)
    print(f'  ✅ 截图保存到: {BIGMAP_PATH} (分辨率: {img.shape[1]}x{img.shape[0]})')

    # Step 3: MSER 检测文字区域
    print('\n[3/4] MSER 检测文字区域...')
    ocr = OCREngine(engine='mser_only')
    results = ocr.recognize(img)
    print(f'  ✅ 检测到 {len(results)} 个文字候选区域')

    if not results:
        print('  ⚠️ 未检测到文字区域，请检查大地图是否正常显示')
        sys.exit(1)

    # 按 y 坐标排序（从上到下）
    results.sort(key=lambda r: r['center'][1])

    print(f'\n  文字区域列表（按从上到下排序）:')
    for i, r in enumerate(results):
        bbox = r['bbox']
        cx, cy = r['center']
        print(f'  [{i:02d}] bbox={bbox}  center=({cx}, {cy})')

    # Step 4: 生成标注图
    print(f'\n[4/4] 生成标注图...')
    annotated = img.copy()
    for i, r in enumerate(results):
        bbox = r['bbox']
        bx, by, bw, bh = bbox
        # 绿色框
        cv2.rectangle(annotated, (bx, by), (bx+bw, by+bh), (0, 255, 0), 2)
        # 编号标签
        cv2.putText(annotated, str(i), (bx, by-5),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imwrite(ANNOTATED_PATH, annotated)
    print(f'  ✅ 标注图保存到: {ANNOTATED_PATH}')

    # Step 5: 生成 config.json 格式的输出
    print(f'\n{"="*60}')
    print('📋 坐标配置输出（复制到 config.json 的 prefecture.prefectures 段）:')
    print('='*60)

    ocr_engine = detect_engine()
    if ocr_engine != 'mser_only':
        # OCR 可用！直接识别
        ocr_online = OCREngine()
        ocr_results = ocr_online.recognize(img, min_conf=0.4)
        pref_list = [r for r in ocr_results if '\u5e9c' in r.get('text', '')]
        print('\n  \u2705 OCR \u8bc6\u522b\u5230\u4ee5\u4e0b\u5dde\u5e9c:')
        for p in pref_list:
            text = p['text']
            cx, cy = p['center']
            print('  "{}": {{"x": {}, "y": {}, "comment": ""}},'.format(text, cx, cy))
    else:
        print('\n  \u26a0\ufe0f  OCR \u5f15\u64ce\u672a\u5b89\u88c5\uff0c\u8bf7\u624b\u52a8\u6253\u5f00\u6807\u6ce8\u56fe\u8bc6\u522b\u5404\u533a\u57df\u5bf9\u5e94\u7684\u5dde\u5e9c')
        print('  \u6807\u6ce8\u56fe\u8def\u5f84:', ANNOTATED_PATH)
        print('\n  \u53c2\u8003\u6a21\u677f\uff08\u8bf7\u624b\u52a8\u66ff\u6362\u540d\u79f0\uff09:')
        # 取面积最大的几个区域作为候选
        for i, r in enumerate(results[:15]):
            bbox = r['bbox']
            cx, cy = r['center']
            print('  "\u5dde\u5e9c\u540d": {{"x": {}, "y": {}, "comment": ""}},  # [{:02d}]'.format(cx, cy, i))


def run_ocr_mode(cfg):
    """OCR 模式：自动识别州府名称并输出坐标。"""
    print('='*60)
    print('模式: PaddleOCR 自动识别')
    print('='*60)

    engine = detect_engine()
    if engine == 'mser_only':
        print('\n❌ OCR 引擎未安装！请先运行:')
        print('   pip install paddlepaddle paddleocr')
        print('   或 python calibrate_map.py  （用 MSER 离线模式）')
        sys.exit(1)

    # Step 1: 进入大地图
    print('\n[1/4] 确保进入大地图...')
    ensure_on_big_map(cfg)

    # Step 2: 截图
    print('\n[2/4] 截取大地图画面...')
    img = ADB.screenshot(save_path=BIGMAP_PATH)
    if img is None:
        print('  ❌ 截图失败')
        sys.exit(1)
    print(f'  ✅ 截图保存到: {BIGMAP_PATH}')

    # Step 3: OCR 识别
    print('\n[3/4] PaddleOCR 识别大地图文字...')
    ocr = OCREngine()
    print(f'  OCR 引擎: {ocr.engine_name}')
    results = ocr.recognize(img, min_conf=0.4)
    print(f'  识别到 {len(results)} 个文字区域')

    # Step 4: 过滤州府名称
    print('\n[4/4] 过滤州府名称（含"府"字）...')
    prefecture_names = []
    for r in results:
        text = r.get('text', '')
        conf = r.get('conf', -1)
        cx, cy = r.get('center', (0, 0))
        if '府' in text or '镇' in text:
            prefecture_names.append({
                'name': text,
                'conf': conf,
                'x': cx,
                'y': cy,
                'bbox': r.get('bbox', (0,0,0,0)),
            })
            print(f'  ✅ {text}  conf={conf:.2f}  center=({cx}, {cy})')

    if not prefecture_names:
        print('  ⚠️  未检测到含"府"/"镇"字的文字区域')
        print('  全部识别结果（前20条）:')
        for r in results[:20]:
            text = r.get('text', '')
            if text:
                print(f'     "{text}"  conf={r.get("conf",-1):.2f}')

    # 生成标注图
    print(f'\n生成标注图...')
    annotated = cv2.imread(BIGMAP_PATH)
    for p in prefecture_names:
        bbox = p['bbox']
        bx, by, bw, bh = bbox
        cv2.rectangle(annotated, (bx, by), (bx+bw, by+bh), (0, 255, 0), 2)
        cv2.putText(annotated, p['name'], (bx, by-5),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.imwrite(ANNOTATED_PATH, annotated)
    print(f'  ✅ 标注图保存到: {ANNOTATED_PATH}')

    # 输出配置
    print(f'\n{"="*60}')
    print('📋 坐标配置（复制到 config.json）:')
    print('='*60)
    for p in prefecture_names:
        print(f'  "{p["name"]}": {{"x": {p["x"]}, "y": {p["y"]}, "comment": ""}},')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='标定大地图州府坐标')
    parser.add_argument('--ocr', action='store_true', help='使用 OCR 模式（需要 PaddleOCR 模型）')
    args = parser.parse_args()

    cfg = load_config()

    try:
        if args.ocr:
            run_ocr_mode(cfg)
        else:
            run_mser_mode(cfg)
    except KeyboardInterrupt:
        print('\n\n⚠️  用户中断')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ 错误: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
