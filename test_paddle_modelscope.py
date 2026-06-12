#!/usr/bin/env python
"""Force PaddleOCR model download using modelscope as source."""
import sys
sys.path.insert(0, r"E:\AI-workspace\JianNanBJT")
import os
import time

# Force modelscope as download source for paddlex
os.environ['PADDLE_MODELS_SOURCE'] = 'modelscope'

# Also set HF mirror
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

print("Testing PaddleOCR init with modelscope source...")
print(f"PADDLE_MODELS_SOURCE={os.environ.get('PADDLE_MODELS_SOURCE', 'not set')}")

from paddleocr import PaddleOCR

start = time.time()
try:
    # Try with explicit smaller/faster model
    ocr = PaddleOCR(
        lang='ch',
        use_doc_orientation_classify=False,
        use_textline_orientation=False,
    )
    elapsed = time.time() - start
    print(f"\n✅ PaddleOCR init OK in {elapsed:.1f}s")
    
    # Now test on a screenshot
    import cv2
    screenshot_dir = r"E:\AI-workspace\JianNanBJT\screenshots"
    for f in ["bigmap_calibrate.png", "bigmap_ocr.png", "big_map_diagnose.png"]:
        path = os.path.join(screenshot_dir, f)
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                print(f"\nRunning OCR on {f}...")
                result = ocr.ocr(img)
                if result and result[0]:
                    print(f"Found {len(result[0])} text regions:")
                    for line in result[0][:30]:
                        box = line[0]
                        text = line[1][0]
                        conf = line[1][1]
                        cx = int(sum(p[0] for p in box) / 4)
                        cy = int(sum(p[1] for p in box) / 4)
                        print(f"  '{text}' conf={conf:.3f} center=({cx},{cy})")
                    
                    # Filter prefecture names
                    pref = [line for line in result[0] if '\u5e9c' in line[1][0]]
                    print(f"\nPrefecture names found: {len(pref)}")
                    for line in pref:
                        text = line[1][0]
                        conf = line[1][1]
                        box = line[0]
                        cx = int(sum(p[0] for p in box) / 4)
                        cy = int(sum(p[1] for p in box) / 4)
                        print(f"  {text} conf={conf:.3f} center=({cx},{cy})")
                else:
                    print("No text found!")
                break
                
except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ PaddleOCR init FAILED after {elapsed:.1f}s: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
