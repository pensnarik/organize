#!/usr/bin/env python3

"""
Scans the source folder for images and moves them into the destination folder
accorinп to their EXIFs and timestamps.

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
           'Apple iPhone': 'iPhone',
           'Apple iPhone 4S': 'iPhone 4S',
           'HighScreen Boost IIse': 'HighScreen',
           'LG Electronics LG-D802': 'LG G2',
           'Canon Canon EOS-1Ds Mark III': 'Canon EOS-1Ds Mark III',
           'HTC HTC Desire 816 dual sim': 'HTC Desire'}

logger = logging.getLogger("organize")

class FileProcessException(Exception):
    pass

class App():

    def __init__(self):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logging.INFO, stream=sys.stdout)

        parser = argparse.ArgumentParser(description='Image organize tool')
        parser.add_argument('--src', type=str, help='Path', required=False)
        parser.add_argument('--dst', type=str, help='Destination', required=False)
        parser.add_argument('--test', action='store_true', default=False)
        parser.add_argument('--file', type=str, help='Processes only a given file in debug mode')
        self.args = parser.parse_args()

        self.args.src = os.path.expanduser(self.args.src)
        self.args.dst = os.path.expanduser(self.args.dst)        

        if self.args.dst is not None:
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
        if exif is None:
            return (None, None)
        if 'DateTimeOriginal' in exif.keys():
            key = 'DateTimeOriginal'
        elif 'DateTime' in exif.keys():
            key = 'DateTime'
        else:
            return (None, None)

        expr_list = {'^(\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2})$': '%Y:%m:%d %H:%M:%S',
                     '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$': '%Y-%m-%d %H:%M:%S'}
        d = None

        for expr in expr_list.keys():
            m = re.search(expr, exif[key])
            if m is not None:
                try:
                    d = dt.strptime(m.group(1), expr_list[expr])
                except ValueError:
                    continue
                break

        return (d, None)

    def get_datetime_from_filename(self, filename):
        basename = os.path.basename(filename)
        # IMG_20160407_193522_HDR_1460046931206.jpg
        expr_list = {'IMG_(\d{8}_\d{6}).(?:jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6}).(?:jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6})_HDR.(?:jpg|jpeg)': '%Y%m%d_%H%M%S',
                     'IMG_(\d{8}_\d{6})_HDR_\d{13}.jpg': '%Y%m%d_%H%M%S',
                     'PANO_(\d{8}_\d{6}).(?:jpg|jpeg)': '%Y%m%d_%H%M%S',
                     '(?:VID|video)_(\d{8}_\d{6}).mp4': '%Y%m%d_%H%M%S',
                     '(\d{8}_\d{6}).(mp4)': '%Y%m%d_%H%M%S',
                     '(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}).jpg': '%Y-%m-%d_%H-%M-%S',
                     'IMG\-(\d{8})-WA\d{4}.(?:jpg|jpeg)': '%Y%m%d',
                     'IMG_(\d{8}_\d{6})_(.*)?\d{13}.jpg': '%Y%m%d_%H%M%S',
                     'IMG_(\d{8}_\d{6})_HHT.jpg': '%Y%m%d_%H%M%S'
                     }
        folder_expr = {'(\d{4}-\d{2}-\d{2})': '%Y-%m-%d',
                       '(\d{2}-\d{2}-\d{4})': '%d-%m-%Y',
                       '(\d{2}\.\d{2}\.\d{2})': '%d.%m.%y'}

        d = None

        # Unix epoch
        if re.match(r'^1(4|5)\d{11}\.(jpg|jpeg|mp4)$', basename):
            m = re.search('^(\d+)\.', basename)
            d = dt.fromtimestamp(int(m.group(1))/1000.0)
            return (d, None)

        for expr in expr_list.keys():
            m = re.search(expr, basename)
            if m is not None:
                try:
                    d = dt.strptime(m.group(1), expr_list[expr])
                except ValueError:
                    raise FileProcessException("Invalid value for date and time in filename")
                return (d, None)

        # Last resort - try to detect date from parents folder name
        if d is None and len(filename.split('/')) > 1:
            parent_folder = filename.split('/')[-2]
            for expr in folder_expr.keys():
                m = re.search(expr, parent_folder)
                if m is not None:
                    try:
                        d = dt.strptime(m.group(1), folder_expr[expr])
                    except ValueError:
                        raise FileProcessException("Invalid value for date in folder name")
                    # Add date to the file name in order not to lose
                    # date/time inforation
                    return (d, '%s-%s' % (d.strftime('%Y-%m-%d'), basename))

        return (d, None)

    def get_datetime(self, filename, exif):
        date_, basename_ = self.get_datetime_from_exif(exif)
        if date_ is None:
            return self.get_datetime_from_filename(filename)
        else:
            return (date_, basename_)

    def get_device_name(self, fullname):
        return MAPPING.get(fullname, fullname)

    def get_time_interval(self, d):
        i = '%s - %s' % (datetime.datetime(d.year, d.month, 1).strftime('%Y-%m-%d'),
                         datetime.datetime(d.year, d.month, monthrange(d.year, d.month)[1]).strftime('%Y-%m-%d'))
        return i

    def get_exif(self, filename):
        try:
            image = Image.open(filename)
        except Exception:
            logger.error("Could not open image")
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
        allowed_extensions = ['jpg', 'jpeg', 'mov', 'mp4', 'webm', '3gp']
        return any(filename.lower().endswith(i) for i in allowed_extensions)

    def get_next_file(self):
        for root, dirs, files in os.walk(self.args.src):
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

    def move_file(self, src, dst, old_dst):
        def add_index_to_filename(filename, index):
            return re.sub('(\.)([^\.]+)$', r'__%0.4d.\2' % index, filename)

        if os.path.exists(old_dst):
            logger.info('RM %s' % old_dst)
            os.remove(old_dst)

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

    def get_path_description(self, filename, exif):
        if self.get_make(exif) is not None and self.get_model(exif) is not None:
            full_device_name = '%s %s' % (self.get_make(exif), self.get_model(exif))
            return self.get_device_name(full_device_name)
        elif exif == {} or exif is None:
            if filename.split('.')[-1] in ('mov', 'mp4', 'webm'):
                return 'Videos'
            else:
                return ''

        return ''

    def process_file(self, filename):
        exif = self.get_exif(filename)
        logger.debug(exif)
        datetime, newbasename = self.get_datetime(filename, exif)

        if datetime is None:
            logger.error("Could not get date and time for file %s", filename)
            return

        if newbasename:
            basename = newbasename
        else:
            basename = os.path.basename(filename)

        time_interval = self.get_time_interval(datetime)
        description = self.get_path_description(filename ,exif)
        dst_path = '%s - %s' % (time_interval, description)
        dst_full_path = os.path.join(self.args.dst, datetime.strftime('%Y'), dst_path)

        if not os.path.exists(dst_full_path) and not self.args.test:
            os.makedirs(dst_full_path)
        if not self.args.test:
            self.move_file(filename, os.path.join(dst_full_path, basename),
                # FIXME: Remove old basename
                os.path.join(dst_full_path, os.path.basename(filename)))
        else:
            logger.info('%s -> %s' % (filename, os.path.join(dst_full_path, basename)))

    def run(self):
        if self.args.file is not None:
            logger.setLevel(logging.DEBUG)
            self.args.test = True
            self.args.dst = '.'
            self.process_file(self.args.file)
            sys.exit(0)

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
