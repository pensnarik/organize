#!/usr/bin/env python3

"""
Scans the source folder for images and moves them into the destination folder
accorind to their EXIFs and timestamps.
"""

import os
import re
import sys
import shutil
import argparse
import datetime
from datetime import datetime as dt
from calendar import monthrange

from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
from PIL.JpegImagePlugin import JpegImageFile

EXCLUDE_EXIF = ['MakerNote', 'UserComment']
MAPPING = {'Xiaomi Redmi Note 7': 'Xiaomi', 'LG Electronics LG-H845': 'LG G5',
           'Apple iPhone 4S': 'iPhone 4S'}

class FileProcessException(Exception):
    pass

class App():

    def __init__(self):
        parser = argparse.ArgumentParser(description='Image organize tool')
        parser.add_argument('--path', type=str, help='Path', required=True)
        parser.add_argument('--dst', type=str, help='Destination', required=True)
        self.args = parser.parse_args()

        if not os.path.exists(self.args.dst) or not os.path.isdir(self.args.dst):
            raise Exception('Destination path does not exist')

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
        if 'DateTimeOriginal' not in exif.keys():
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

    def get_device_name(self, fullname):
        return MAPPING.get(fullname, fullname)

    def get_time_interval(self, filename, exif):
        basename = os.path.basename(filename)
        expr_list = {'IMG_(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6})_HDR.(jpg|jpeg)': '%Y%m%d_%H%M%S',
                     'PANO_(\d{8}_\d{6}).(jpg|jpeg)': '%Y%m%d_%H%M%S'}
        d = None

        for expr in expr_list.keys():
            m = re.search(expr, basename)
            if m is not None:
                d = dt.strptime(m.group(1), expr_list[expr])
                break

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

    def get_next_file(self):
        for root, dirs, files in os.walk(self.args.path):
            for file in files:
                yield os.path.join(root, file)

    def process_file(self, filename):
        exif = self.get_exif(filename)
        basename = os.path.basename(filename)
        full_device_name = '%s %s' % (exif.get('Make'), exif.get('Model'))
        time_interval = self.get_time_interval(filename, exif)
        dst_path = '%s - %s' % (time_interval, self.get_device_name(full_device_name))
        dst_full_path = os.path.join(self.args.dst, dst_path)
        if not os.path.exists(dst_full_path):
            os.mkdir(dst_full_path)
        print('%s -> %s' % (filename, os.path.join(dst_full_path, basename)))
        shutil.move(filename, os.path.join(dst_full_path, basename))

    def run(self):
        for file in self.get_next_file():
            try:
                self.process_file(file)
            except FileProcessException:
                print('Skipping %s' % file)

if __name__ == '__main__':
    app = App()
    sys.exit(app.run())
