#!/usr/bin/env python3

"""
Removes duplicates
"""

import os
import sys
import argparse

from organize.pcp_hash import get_file_hash, get_pcp_hash, get_file_size

class App():

    src_hashes = {}
    dst_hashes = {}

    def __init__(self):
        parser = argparse.ArgumentParser(description='Duplicate remove tool')
        parser.add_argument('--src', type=str, help='Path', required=False)
        parser.add_argument('--dst', type=str, help='Destination', required=False)
        self.args = parser.parse_args()

        self.args.src = os.path.expanduser(self.args.src)
        self.args.dst = os.path.expanduser(self.args.dst)

    def build_hash(self, path, ignore_path=None):
        result = {}
        for root, dirs, files in os.walk(path):
            for file in files:
                print(file)
                if not file.split('.')[-1].lower() in ['jpg', 'jpeg', 'png']:
                    continue

                filename = os.path.join(root, file)

                if ignore_path is not None and filename.startswith(ignore_path):
                    continue

                hash = get_pcp_hash(filename)

                if hash in result.keys():
                    result[hash].append(filename)
                else:
                    result[hash] = [filename]

        return result

    def run(self):

        self.src_hashes = self.build_hash(self.args.src)
        self.dst_hashes = self.build_hash(self.args.dst, self.args.src)

        print(self.src_hashes)
        print(self.dst_hashes)

        for hash in self.src_hashes.keys():
            if hash in self.dst_hashes.keys():
                print("RM %s: %s" % (hash, self.src_hashes[hash]))
                for file in self.src_hashes[hash]:
                    os.remove(file)

if __name__ == '__main__':
    app = App()
    sys.exit(app.run())
