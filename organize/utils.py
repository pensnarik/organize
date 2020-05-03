# Utils

import os
import re
import shutil
import logging

logger = logging.getLogger("organize")

def add_index_to_filename(filename, index):
    return re.sub('(\.)([^\.]+)$', r'__%0.4d.\2' % index, filename)

def safe_move(src, dst):
    i = 2
    while os.path.exists(add_index_to_filename(dst, i)):
        i += 1
    logger.info('MV %s -> %s', src, add_index_to_filename(dst, i))
    shutil.move(src, add_index_to_filename(dst, i))
