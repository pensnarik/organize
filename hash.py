#!/usr/bin/env python3

import sys

from organize.pcp_hash import get_file_hash, get_pcp_hash

if len(sys.argv) != 2:
    print("Usage: hash.py filename")
    sys.exit(2)

filename = sys.argv[1]

print("md5_hash: %s" % get_file_hash(filename))
print("PCP hash: %s" % get_pcp_hash(filename))
