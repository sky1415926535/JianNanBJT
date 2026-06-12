#!/usr/bin/env python
"""Quick OCR test on existing bigmap screenshot."""
import sys
sys.path.insert(0, r"E:\AI-workspace\JianNanBJT")
from common.ocr import OCREngine, detect_engine
import cv2
import os

print(f"Engine detected: {detect_engine()}")
ocr = OCREngine()
print(f"Engine name: {ocr.engine_name}")

# Try multiple screenshot paths
screenshot_dir = r"E:\AI-workspace\JianNanBJT\screenshots"
test_files = ["bigmap_calibrate.png", "bigmap_ocr.png", "big_map_diagnose.png"]

img = None
for f in test_files:
    path = os.path.join(screenshot_dir, f)
    if os.path.exists(path):
        img = cv2.imread(path)
        if img is not None:
            print(f"Using screenshot: {f}")
            break

if img is None:
    print("ERROR: Cannot find a bigmap screenshot to test")
    sys.exit(1)

print(f"Image shape: {img.shape}")

# Run OCR
results = ocr.recognize(img, min_conf=0.4)
print(f"Found {len(results)} text regions")

for r in results:
    text = r.get("text", "")
    conf = r.get("conf", -1)
    if text:
        print(f"  Text: '{text}' conf={conf:.3f} center={r['center']}")
    elif len(results) <= 20:
        bbox = r.get("bbox", (0, 0, 0, 0))
        print(f"  [MSER region] bbox={bbox} center={r['center']}")

# List prefecture names
pref_names = [r for r in results if "\u5e9c" in r.get("text", "")]
print(f"\nPrefecture names found: {len(pref_names)}")
for p in pref_names:
    print(f"  {p['text']} conf={p['conf']:.3f} center={p['center']}")
