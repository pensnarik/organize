# Image perceptual hashing algorithm

import os
import math
import hashlib
import subprocess

from PIL import Image

def get_file_size(filename):
    statinfo = os.stat(filename)
    return statinfo.st_size

def get_file_hash(filename):
    # Returns file md5 hash
    with open(filename, 'rb') as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    return md5

def get_pcp_hash_dir():
    return os.path.expanduser("~/.pcp_hash")

def get_pcp_hash(filename):
    md5_hash = get_file_hash(filename)

    command = 'convert -depth 8 -strip -type Grayscale -geometry 8x8! "%s" "%s/%s.png"' % \
              (filename, get_pcp_hash_dir(), md5_hash)

    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        return '0000000000000000'

    im = Image.open('%s/%s.png' % (get_pcp_hash_dir(), md5_hash,))
    width, height = im.size

    if width != height:
        raise Exception('Width != height')

    sum = 0

    for y in range(0, height):
        for x in range(0, width):
            pixel = im.getpixel((x, y))
            sum += pixel

    average = sum / (width*height)

    hash = list()

    for y in range(0, width):
        bits = 0
        for x in range(0, height):
            bit = int(im.getpixel((x, y)) > average)
            bits += bit * math.pow(2, 7 - x)
        hash.append(int(bits))

    hash_as_str = ''.join(['%.2x' % i for i in hash])

    #os.system('rm %s/%s.png' % (get_pcp_hash_dir(), md5_hash))

    return hash_as_str
