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
from logging import FileHandler
import argparse
import datetime
from hashlib import md5 as md5_hash
from datetime import datetime as dt
from calendar import monthrange

from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS
from PIL.JpegImagePlugin import JpegImageFile

from organize.pcp_hash import get_file_hash, get_pcp_hash, get_file_size

EXCLUDE_EXIF = ['MakerNote', 'UserComment']
MAPPING = {'Xiaomi Redmi Note 7': 'Xiaomi', 'LG Electronics LG-H845': 'LG G5',
           'Apple iPhone': 'iPhone',
           'Apple TIFFMODEL_IPHONE': 'iPhone',
           'Apple iPhone 4S': 'iPhone 4S',
           'HighScreen Boost IIse': 'HighScreen',
           'LG Electronics LG-D802': 'LG G2',
           'Canon Canon EOS-1Ds Mark III': 'Canon EOS-1Ds Mark III',
           'HTC HTC Desire 816 dual sim': 'HTC Desire',
           'OLYMPUS OPTICAL CO.,LTD C120,D380': 'Olympus C120',
           '2006-04-01 - 2006-04-30 - CASIO COMPUTER CO.,LTD  EX-S100': 'Casio EX-S100'}

logger = logging.getLogger("organize")

class FileProcessException(Exception):
    pass

class App():

    def __init__(self):
        self.setup_logging()
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

    def setup_logging(self):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logging.INFO, stream=sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = FileHandler('organize-%s.log' % dt.now().strftime('%Y%m%d_%H%M%S'))
        handler.setFormatter(formatter)
        logger.addHandler(handler)

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
            return None
        if 'DateTimeOriginal' in exif.keys():
            key = 'DateTimeOriginal'
        elif 'DateTime' in exif.keys():
            key = 'DateTime'
        else:
            return None

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

        return d

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
            return d

        for expr in expr_list.keys():
            m = re.search(expr, basename)
            if m is not None:
                try:
                    d = dt.strptime(m.group(1), expr_list[expr])
                except ValueError:
                    raise FileProcessException("Invalid value for date and time in filename")
                return d

        # Last resort - try to detect date from parents folder name
        if d is None and len(filename.split('/')) > 1:
            parent_folder = filename.split('/')[-2]
            for expr in folder_expr.keys():
                m = re.search(expr, parent_folder)
                if m is not None:
                    try:
                        d = dt.strptime(m.group(1), folder_expr[expr])
                        if d.year < 2001 or d.year > 2020:
                            logger.error("Invalid year folder name: %s", parent_folder)
                            return None
                    except ValueError:
                        raise FileProcessException("Invalid value for date in folder name")
                    # Add date to the file name in order not to lose
                    # date/time inforation
                    logger.info("Got date and time from parent's folder name")
                    return d

        return d

    def get_datetime(self, filename, exif):
        date_ = self.get_datetime_from_exif(exif)
        if date_ is None:
            return self.get_datetime_from_filename(filename)
        else:
            return date_

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

    def get_remove_candidate(self, file1, file2):
        # Determines which file to delete based on file contents
        logger.info("Choosing remove candidate between \"%s\" and \"%s\"", file1, file2)

        os.system("jhead -q -autorot \"%s\"" % file1)
        os.system("jhead -q -autorot \"%s\"" % file2)

        pcp_hash1 = get_pcp_hash(file1)
        pcp_hash2 = get_pcp_hash(file2)

        if pcp_hash1 != pcp_hash2:
            logger.info("Files have different PCP hashes, keeping both (%s != %s)", pcp_hash1,
                        pcp_hash2)
            return None

        if pcp_hash1 == '0000000000000000':
            return None

        logger.info("Files PCP hashes are equal: %s", pcp_hash1)
        # If images are equal, we keep the best one
        im1 = Image.open(file1)
        im2 = Image.open(file2)
        w1, h1 = im1.size
        w2, h2 = im2.size

        if w1/h1 != w2/h2:
            logger.warning("Images proportions are differ")
            return None

        if w1*h1 > w2*h2 and self.get_exif(file1) != {}:
            logger.info('file1 is larger and contains EXIF')
            return file2
        elif w2*h2 > w1*h1 and self.get_exif(file2) != {}:
            logger.info('file2 is larger and contains EXIF')
            return file1
        elif w1*h1 == w2*h2 and self.get_exif(file1) != {} and self.get_exif(file2) != {}:
            logger.info("Images have the same geometry, comparing file sizes")
            if get_file_size(file1) > get_file_size(file2):
                return file2
            else:
                return file1
        else:
            return None

    def move_file(self, src, dst):
        if not os.path.exists(dst):
            # If dst doesn't exist just move src to dst
            logger.info('MV %s -> %s', src, dst)
            shutil.move(src, dst)
        elif get_file_hash(src) == get_file_hash(dst):
            # If it exists and it's the same file - remove src
            logger.info('RM %s' % src)
            os.remove(src)
        else:
            # If both are exist and differ - check their perceptual hashes
            # and sizes, maybe we can determine which one is better, if not -
            # we move with a different name
            remove = self.get_remove_candidate(src, dst)

            if remove is not None:
                logger.warning("Removing duplicate image")
                logger.warning("RM %s", remove)
                os.remove(remove)
                if remove == dst:
                    logger.info('MV %s -> %s', src, dst)
                    shutil.move(src, dst)    
            else:
                # Move it with a different name
                safe_move(src, dst)

    def get_path_description(self, filename, exif):
        if self.get_make(exif) is not None and self.get_model(exif) is not None:
            full_device_name = '%s %s' % (self.get_make(exif), self.get_model(exif))
            return self.get_device_name(full_device_name)
        elif exif == {} or exif is None:
            if filename.split('.')[-1].lower() in ('mov', 'mp4', 'webm'):
                return 'Videos'
            else:
                return ''

        logger.error("Could not get path description")
        return ''

    def get_new_basename(self, datetime, filename):
        assert datetime is not None

        ext = filename.split('.')[-1].lower()

        if datetime.strftime('%H%M%S') == '000000':
            time_part = re.sub(r'\(\d+\)$',
                               '',
                               '.'.join(os.path.basename(filename).split('.')[:-1]))
        else:
            time_part = datetime.strftime('%H%M%S')

        return '%s_%s.%s' % (datetime.strftime('%Y%m%d'), time_part, ext)

    def process_file(self, filename):
        logger.info("Processing file %s", filename)
        exif = self.get_exif(filename)
        logger.debug(exif)
        datetime = self.get_datetime(filename, exif)

        if datetime is None:
            logger.error("Could not get date and time for file %s", filename)
            return

        basename = self.get_new_basename(datetime, filename)

        time_interval = self.get_time_interval(datetime)
        description = self.get_path_description(filename ,exif)

        if description != '':
            dst_path = '%s - %s' % (time_interval, description)
        else:
            dst_path = time_interval

        dst_full_path = os.path.join(self.args.dst, datetime.strftime('%Y'), dst_path)

        if not os.path.exists(dst_full_path) and not self.args.test:
            os.makedirs(dst_full_path)
        if not self.args.test:
            self.move_file(filename, os.path.join(dst_full_path, basename))
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
