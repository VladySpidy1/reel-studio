"""Contact sheet of PNG/JPG stills: python sheet.py out.jpg cols w h files..."""
import sys
from pathlib import Path

import cv2
import numpy as np

out, cols, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
files = sys.argv[5:]
ims = []
for f in files:
    im = cv2.resize(cv2.imread(f), (w, h), interpolation=cv2.INTER_AREA)
    cv2.putText(im, Path(f).stem, (8, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    ims.append(im)
while len(ims) % cols:
    ims.append(np.zeros_like(ims[0]))
rows = [np.hstack(ims[i:i + cols]) for i in range(0, len(ims), cols)]
cv2.imwrite(out, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])
