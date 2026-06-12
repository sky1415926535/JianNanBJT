"""
搜索并标定宁波府在大地图上的坐标
螺旋搜索策略：up×3, left×3, down×3, right×3 ...
找到后自动写入 config.json
"""
import time, json, cv2, numpy as np, logging
from common import ADB, load_config, Vision
from common.ocr import OCREngine
from rapidocr import RapidOCR

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('find_ningbo')

cfg = load_config()
ADB.adb_path = cfg['adb']['path']
ADB.device = cfg['adb'].get('device_id')
pref_cfg = cfg.get('prefecture', {})

SWIPE_DIST = 400
SWIPE_INTER = 1.5
MAX_SWIPES = 20

def swipe_map(direction, distance=SWIPE_DIST):
    w, h = 1920, 1080
    cx, cy = w // 2, h // 2
    half = distance // 2
    mapping = {
        "up":    (cx, cy + half, cx, cy - half),
        "down":  (cx, cy - half, cx, cy + half),
        "left":  (cx + half, cy, cx - half, cy),
        "right": (cx - half, cy, cx + half, cy),
    }
    sx, sy, ex, ey = mapping[direction]
    ADB.swipe(sx, sy, ex, ey, 400)
    log.info(f'[滑动] {direction} {distance}px')

def ocr_find_prefecture(img, target='宁波府'):
    """用 OCR 找目标州府，返回 (cx, cy) 或 None"""
    ocr = RapidOCR()
    result = ocr(img)
    if result is None:
        return None
    txts = result.txts if hasattr(result, 'txts') else (result[1] if isinstance(result, (list,tuple)) and len(result)>1 else [])
    boxes = result.boxes if hasattr(result, 'boxes') else (result[0] if isinstance(result, (list,tuple)) else [])
    scores = result.scores if hasattr(result, 'scores') else (result[2] if isinstance(result, (list,tuple)) and len(result)>2 else [])
    
    for i, txt in enumerate(txts):
        if target in txt or ('宁波' in target and ('宁' in txt or '波' in txt)):
            box = np.array(boxes[i], dtype=int)
            cx = int(box[:,0].mean())
            cy = int(box[:,1].mean())
            conf = scores[i] if i < len(scores) else 0.0
            return (cx, cy, conf, txt)
    return None

def spiral_directions(n=20):
    """生成螺旋搜索方向序列: up×3, left×3, down×3, right×3, ..."""
    dirs = ['up', 'left', 'down', 'right']
    seq = []
    for d in dirs:
        seq.extend([d] * 3)
    # 如果不够，重复
    while len(seq) < n:
        seq.extend(seq[:min(n-len(seq), len(seq))])
    return seq[:n]

# ============ 主流程 ============

# 1. 确保在大地图
log.info('[步骤1] 确保进入大地图...')
enter_btn = pref_cfg.get('big_map_enter_btn', {})
menu_btn = pref_cfg.get('big_map_menu_btn', {})
ex, ey = enter_btn.get('x', 108), enter_btn.get('y', 908)
mx, my = menu_btn.get('x', 218), menu_btn.get('y', 389)

ADB.tap(ex, ey)
time.sleep(0.5)
ADB.tap(mx, my)
time.sleep(3)
log.info('  已点击进入大地图')

# 2. 螺旋搜索
log.info(f'[步骤2] 开始螺旋搜索（最多{MAX_SWIPES}次）...')
spiral = spiral_directions(MAX_SWIPES)

for i in range(MAX_SWIPES + 1):  # +1 是为了搜索初始视口
    img = ADB.screenshot()
    if img is None:
        log.warning('截图失败，重试...')
        time.sleep(1)
        continue
    
    # OCR 搜索
    found = ocr_find_prefecture(img, '宁波府')
    if found:
        cx, cy, conf, txt = found
        log.info(f'✅ 第{i}轮找到宁波府！识别="{txt}" 坐标=({cx},{cy}) 置信度={conf:.2f}')
        
        # 点击确认
        log.info(f'点击坐标 ({cx}, {cy})...')
        ADB.tap(cx, cy)
        time.sleep(pref_cfg.get('popup_wait', 1.0))
        
        # 处理确认弹窗
        img2 = ADB.screenshot()
        vision = Vision()
        red_btns = vision.find_red_buttons(img2)
        confirm_btns = [b for b in red_btns if not (b[1] > 800 and b[0] < 300)]
        if confirm_btns:
            bx, by = confirm_btns[0][0], confirm_btns[0][1]
            log.info(f'点击确认按钮 ({bx}, {by})')
            ADB.tap(bx, by)
            time.sleep(3)
        
        # 等待加载
        time.sleep(pref_cfg.get('loading_wait', 2.0))
        
        # 写入 config.json
        log.info('[步骤3] 写入 config.json...')
        with open('config.json') as f:
            cfg_data = json.load(f)
        
        if '宁波府' not in cfg_data['prefecture']['prefectures']:
            cfg_data['prefecture']['prefectures']['宁波府'] = {}
        
        cfg_data['prefecture']['prefectures']['宁波府']['map_coord'] = {
            'x': cx,
            'y': cy,
            'scroll_x': 0,  # 暂时不记录滚动偏移，后续可以补充
            'scroll_y': 0,
            'click_offset_y': 60,
            'comment': f'大地图坐标【OCR标定】- 螺旋搜索第{i}轮'
        }
        
        with open('config.json', 'w') as f:
            json.dump(cfg_data, f, ensure_ascii=False, indent=2)
        log.info(f'✅ 已写入 config.json: 宁波府 map_coord=({cx},{cy})')
        
        # 返回城镇视图
        log.info('[步骤4] 返回城镇视图...')
        ADB.press_back()
        time.sleep(2)
        
        log.info('===== 完成！宁波府已标定并切换成功 =====')
        exit(0)
    
    # 本轮未找到，输出诊断信息
    ocr_tmp = RapidOCR()
    result_tmp = ocr_tmp(img)
    if result_tmp is not None:
        txts_tmp = result_tmp.txts if hasattr(result_tmp, 'txts') else []
        prefs_tmp = [t for t in txts_tmp if '府' in t or '镇' in t]
        log.info(f'  第{i}轮未找到，当前视口有: {prefs_tmp[:5]}')
    
    # 滑动（最后一轮不滑动）
    if i < MAX_SWIPES:
        direction = spiral[i]
        log.info(f'  未找到，向 {direction} 滑动...')
        swipe_map(direction)
        time.sleep(SWIPE_INTER)

log.error(f'❌ 搜索{MAX_SWIPES}次仍未找到宁波府')
log.error('建议：1) 检查宁波府名称是否正确  2) 增加 MAX_SWIPES')
