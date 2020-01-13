#!/usr/bin/env python3

"""
Scans the source folder for images and moves them into the destination folder
accorind to their EXIFs and timestamps.

organize.py never overwrites existing files in --dst
"""

import os
import re
import sys
import shutil
import logging
import argparse
import datetime
from hashlib import md5 as md5_hash
from datetime import datetime as dt
from calendar import monthrange

from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
from PIL.JpegImagePlugin import JpegImageFile

EXCLUDE_EXIF = ['MakerNote', 'UserComment']
MAPPING = {'Xiaomi Redmi Note 7': 'Xiaomi', 'LG Electronics LG-H845': 'LG G5',
           'Apple iPhone 4S': 'iPhone 4S', 'HighScreen Boost IIse': 'HighScreen',
           'LG Electronics LG-D802': 'LG G2'}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("organize")

class FileProcessException(Exception):
    pass

class App():

    def __init__(self):
        parser = argparse.ArgumentParser(description='Image organize tool')
        parser.add_argument('--path', type=str, help='Path', required=True)
        parser.add_argument('--dst', type=str, help='Destination', required=True)
        parser.add_argument('--test', action='store_true', default=False)
        self.args = parser.parse_args()

        if not os.path.exists(self.args.dst) or not os.path.isdir(self.args.dst):
            raise Exception('Destination path does not exist')

        logger.setLevel(logging.ERROR)

    def exif2text(self, value):
        """ Helper function """
        if isinstance(value, str):
            result = str(value)
        elif isinstance(value, int):
            result = str(value)
        elif isinstance(value, bytes):
            result = value.hex()
        else:
            result = str(value)

        return result.replace('\u0000', '')

    def get_datetime_from_exif(self, exif):
        if exif is None or 'DateTimeOriginal' not in exif.keys():
            return None

        expr_list = {'^(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})$': '%Y:%m:%d %H:%M:%S',
                     '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$': '%Y-%m-%d %H:%M:%S'}
        d = None

        for expr in expr_list.keys():
            m = re.search(expr, exif['DateTimeOriginal'])
            if m is not None:
                d = dt.strptime(m.group(1), expr_list[expr])
                break

        return d

    def get_datetime_from_filename(self, filename):
        basename = os.path.basename(filename)
        expr_list = {'IMG_(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6})_HDR.(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     'PANO_(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(VID|video?)_(\d{8}_\d{6}).(mp4)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6}).(mp4)': '%Y%m%d_%H%M%S',
                     '(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}).jpg': '%Y-%m-%d_%H-%M-%S'}
        d = None

        for expr in expr_list.keys():
            m = re.search(expr, basename)
            if m is not None:
                try:
                    d = dt.strptime(m.group(1), expr_list[expr])
                except ValueError:
                    raise FileProcessException("Invalid value for date and time in filename")
                break

        return d

    def get_datetime(self, filename, exif):
        return self.get_datetime_from_exif(exif) or \
               self.get_datetime_from_filename(filename)

    def get_device_name(self, fullname):
        return MAPPING.get(fullname, fullname)

    def get_time_interval(self, filename, exif):
        d = self.get_datetime_from_filename(filename)

        if d is None:
            # Try to get date and time from EXIF
            d = self.get_datetime_from_exif(exif)

        if d is None:
            raise FileProcessException('Cannot get datetime')

        i = '%s - %s' % (datetime.datetime(d.year, d.month, 1).strftime('%Y-%m-%d'),
                         datetime.datetime(d.year, d.month, monthrange(d.year, d.month)[1]).strftime('%Y-%m-%d'))
        return i

    def get_exif(self, filename):
        try:
            image = Image.open(filename)
        except Exception:
            return {}

        if isinstance(image, JpegImageFile) and image._getexif() is not None:
            info = image._getexif()
            exif = {}
            for tag, value in info.items():
                decoded = TAGS.get(tag, tag)
                if decoded in EXCLUDE_EXIF:
                    continue
                else:
                    exif[decoded] = self.exif2text(value)
        else:
            exif = {}

        return exif

    def filter(self, filename):
        allowed_extensions = ['jpg', 'jpeg', 'mov', 'mp4', 'webm']
        return any(filename.endswith(i) for i in allowed_extensions)

    def get_next_file(self):
        for root, dirs, files in os.walk(self.args.path):
            for file in files:
                if self.filter(os.path.join(root, file)):
                    yield os.path.join(root, file)

    def get_make(self, exif):
        return exif.get('Make') or exif.get('Camera make')

    def get_model(self, exif):
        return exif.get('Model') or exif.get('Camera model')

    def get_file_hash(self, filename):
        with open(filename, 'rb') as f:
            md5 = md5_hash(f.read()).hexdigest()
        return md5

    def move_file(self, src, dst):
        def add_index_to_filename(filename, index):
            return re.sub('(\.)([^\.]+)$', r'__%0.4d.\2' % index, filename)

        if not os.path.exists(dst):
            # If dst doesn't exist just move src to dst
            logger.info('MV %s -> %s', src, dst)
            shutil.move(src, dst)
        elif self.get_file_hash(src) == self.get_file_hash(dst):
            # If it exists and it's the same file - remove src
            logger.info('RM %s' % src)
            os.remove(src)
        else:
            # If both are exist and differ - move with a different name
            i = 2
            while os.path.exists(add_index_to_filename(dst, i)):
                i += 1
            logger.info('MV %s -> %s', src, add_index_to_filename(dst, i))
            shutil.move(src, add_index_to_filename(dst, i))

    def process_file(self, filename):
        exif = self.get_exif(filename)
        datetime = self.get_datetime(filename, exif)

        if datetime is None:
            logger.error("Could not get date and time for file %s", filename)
            return

        basename = os.path.basename(filename)
        full_device_name = '%s %s' % (self.get_make(exif), self.get_model(exif))
        time_interval = self.get_time_interval(filename, exif)
        dst_path = '%s - %s' % (time_interval, self.get_device_name(full_device_name))
        dst_full_path = os.path.join(self.args.dst, datetime.strftime('%Y'), dst_path)

        if not os.path.exists(dst_full_path) and not self.args.test:
            os.makedirs(dst_full_path)
        if not self.args.test:
            self.move_file(filename, os.path.join(dst_full_path, basename))
        else:
            logger.info('%s -> %s' % (filename, os.path.join(dst_full_path, basename)))

    def run(self):
        for file in self.get_next_file():
            try:
                self.process_file(file)
            except FileProcessException:
                logger.error('Skipping %s' % file)
            except:
                logger.error("Unhandled exception while processing file %s" % file)
                raise

if __name__ == '__main__':
    app = App()
    sys.exit(app.run())
