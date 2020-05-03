#!/usr/bin/env python3

import os
import sys
import shutil

from PIL import Image

from organize.pcp_hash import get_file_hash
from organize.utils import safe_move

SCREENSHOTS = ((533, 800), (540, 800), (640, 960), (640, 1136), (720, 1280))

for root, dir, files in os.walk(sys.argv[1]):
    for file in files:
        filename = os.path.join(root, file)
        try:
            im = Image.open(filename)
        except Exception:
            continue
        w, h = im.size
        if w == h:
            print("%s: %s" % (filename, (w, h,)))
            hash = get_file_hash(filename)
            extension = filename.split('.')[-1]
            newf = os.path.join(os.path.expanduser("~/Pictures/archive/square"),
                                "%s.%s" % (hash, extension))
            shutil.move(filename, newf)
        if (w, h) in SCREENSHOTS:
            newf = os.path.join(os.path.expanduser("~/Pictures/archive/screenshots"),
                                "%s" % os.path.basename(filename))
            print("%s -> %s" % (filename, newf))
            safe_move(filename, newf)

        if filename.lower().endswith('.png'):
            hash = get_file_hash(filename)
            newf = os.path.join(os.path.expanduser("~/Pictures/archive/png"), "%s.png" % hash)
            print("%s -> %s" % (filename, newf))
            shutil.move(filename, newf)
