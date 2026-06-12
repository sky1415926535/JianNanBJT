import time, json, cv2, numpy as np
from common import ADB, load_config, Vision
from rapidocr import RapidOCR

cfg = load_config()
ADB.adb_path = cfg['adb']['path']
ADB.device = cfg['adb'].get('device_id')
pref_cfg = cfg.get('prefecture', {})

# 进入大地图
enter_btn = pref_cfg.get('big_map_enter_btn', {})
menu_btn = pref_cfg.get('big_map_menu_btn', {})
enter_x, enter_y = enter_btn.get('x', 108), enter_btn.get('y', 908)
menu_x, menu_y = menu_btn.get('x', 218), menu_btn.get('y', 389)

print('[1] 点击州府印...')
ADB.tap(enter_x, enter_y)
time.sleep(0.5)

print('[2] 点击大地图按钮...')
ADB.tap(menu_x, menu_y)
time.sleep(3)

# 截图并OCR
img = ADB.screenshot()
if img is None:
    print('截图失败')
    exit(1)

cv2.imwrite('screenshots/debug_bigmap_for_ningbo.png', img)
print('大地图截图已保存')

# OCR搜索宁波府
ocr = RapidOCR()
result = ocr(img)
print(f'\nOCR识别到 {len(result.txts)} 条文字')

# 找所有含府/镇/州/波/宁的文字
target_keywords = ['府', '镇', '州', '波', '宁', '应', '扬', '杭', '苏', '松', '徽', '绍', '宁']
found = []
for i, txt in enumerate(result.txts):
    for kw in target_keywords:
        if kw in txt:
            box = np.array(result.boxes[i], dtype=int)
            cx, cy = int(box[:,0].mean()), int(box[:,1].mean())
            found.append((txt, cx, cy, result.scores[i]))
            break

print(f'\n找到 {len(found)} 个相关文字:')
for txt, cx, cy, score in found:
    print(f'  [{score:.2f}] "{txt}" @ ({cx},{cy})')

# 检查宁波府
has_nb = any('波' in t[0] or '宁' in t[0] for t in found)
if has_nb:
    print('\n✅ 宁波府在当前视口！')
else:
    print('\n❌ 宁波府不在当前视口，需要滑动搜索')
