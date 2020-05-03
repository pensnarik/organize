# Image perceptual hashing algorithm

import os
import math
import hashlib
import subprocess

from PIL import Image

# Size of image perceptive hash, in bits, required to meet 2 conditions:
# 1) Should be power of 2
# 2) log(PCP_HASH_SIZE, 2) should be interger
# Possible values are: 2, 4, 16, 64, 256, 1024, 4096, 16384, ...
PCP_HASH_SIZE = 256

PCP_THUMB_SIZE = int(math.sqrt(PCP_HASH_SIZE))
PCP_BITS_PER_ROW = PCP_THUMB_SIZE

def get_file_size(filename):
    statinfo = os.stat(filename)
    return statinfo.st_size

def get_file_hash(filename):
    # Returns file md5 hash
    with open(filename, 'rb') as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    return md5

def get_hash_filename(md5_hash):
    return os.path.join(get_pcp_hash_dir(), '%s.hash' % md5_hash)

def get_pcp_hash_dir():
    return os.path.expanduser("~/.pcp_hash")

def get_pcp_hash(filename):
    # TODO
    # Consider referring to this for more optimal algorithm
    # http://www.ruanyifeng.com/blog/2011/07/imgHash.txt?spm=a2c65.11461447.0.0.1c8c3588zsrYlA&file=imgHash.txt
    md5_hash = get_file_hash(filename)

    if os.path.exists(get_hash_filename(md5_hash)):
        return open(get_hash_filename(md5_hash), 'rt').read()

    command = 'convert -depth 8 -strip -type Grayscale -geometry %sx%s! "%s" "%s/%s.png"' % \
              (PCP_THUMB_SIZE, PCP_THUMB_SIZE, filename, get_pcp_hash_dir(), md5_hash)

    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        return None

    im = Image.open('%s/%s.png' % (get_pcp_hash_dir(), md5_hash))
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
            bits += bit * math.pow(2, PCP_BITS_PER_ROW - 1 - x)

        hash.append(int(bits))

    # We need (PCP_BITS_PER_ROW / 8 * 2) symbols to store a row as a hex string
    # It's (PCP_BITS_PER_ROW / 8) bytes, and 2 characters per byte ('00' - 'ff')
    format_str = '%.{}x'.format(int(PCP_BITS_PER_ROW / 8 * 2))
    hash_as_str = ''.join([format_str % i for i in hash])

    with open(get_hash_filename(md5_hash), 'wt') as f:
        f.write(hash_as_str)

    os.system('rm %s/%s.png' % (get_pcp_hash_dir(), md5_hash))

    return hash_as_str
