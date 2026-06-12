#!/usr/bin/env python
"""Test PaddleOCR with simplified pipeline (v4 models)."""
import sys
sys.path.insert(0, r"E:\AI-workspace\JianNanBJT")
import cv2
import os
import time

print("Testing PaddleOCR 3.x initialization...")
try:
    from paddleocr import PaddleOCR
    start = time.time()
    
    # Try different init approaches
    print("Attempt 1: Simplest init...")
    ocr = PaddleOCR(
        use_doc_orientation_classify=False,
        use_textline_orientation=False,
    )
    elapsed = time.time() - start
    print(f"Init took {elapsed:.1f}s")
    
    # Load test image
    screenshot_dir = r"E:\AI-workspace\JianNanBJT\screenshots"
    for f in ["bigmap_calibrate.png", "bigmap_ocr.png", "big_map_diagnose.png"]:
        path = os.path.join(screenshot_dir, f)
        if os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                print(f"\nUsing screenshot: {f} ({img.shape[1]}x{img.shape[0]})")
                
                # Run OCR
                start = time.time()
                result = ocr.ocr(img)
                elapsed = time.time() - start
                print(f"OCR took {elapsed:.1f}s")
                
                if result and result[0]:
                    print(f"Found {len(result[0])} text regions:")
                    for line in result[0][:20]:
                        box = line[0]
                        text = line[1][0]
                        conf = line[1][1]
                        cx = int(sum(p[0] for p in box) / 4)
                        cy = int(sum(p[1] for p in box) / 4)
                        print(f"  '{text}' conf={conf:.3f} center=({cx},{cy})")
                    
                    # Filter prefecture names
                    pref = [(line[1][0], line[1][1], line[0]) for line in result[0] if "\u5e9c" in line[1][0]]
                    print(f"\nPrefecture names found: {len(pref)}")
                    for text, conf, box in pref:
                        cx = int(sum(p[0] for p in box) / 4)
                        cy = int(sum(p[1] for p in box) / 4)
                        print(f"  {text} conf={conf:.3f} center=({cx},{cy})")
                else:
                    print("No text found!")
                break
    else:
        print("ERROR: No screenshot found")
        
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
