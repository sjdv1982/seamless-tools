#!/usr/bin/env -S python3 -u

# TODO: document

import json
import os
import sys

os.environ["__SEAMLESS_FRUGAL"] = "1"

import seamless
from seamless import Checksum
from seamless.config import database, AssistantConnectionError
from seamless.cmd.bytes2human import bytes2human

from seamless.cmd.message import message_and_exit as err
from seamless.cmd.file_load import read_checksum_file

import argparse

parser = argparse.ArgumentParser(
    prog="seamless-buffer-size",
    description="Get the buffer size of one or more checksum files",
)

parser.add_argument(
    "-H",
    "--human-readable",
    dest="human_readable",
    help="Print sizes in human readable format (e.g. 1kB)",
    action="store_true",
)

parser.add_argument(
    "-d",
    "--deep",
    "--dict",
    dest="is_dict",
    help="Checksum file is a deep cell (dict of checksums)",
    action="store_true",
)

parser.add_argument(
    "-l",
    "--list",
    dest="is_list",
    help="Checksum file is a JSON list of checksums",
    action="store_true",
)

parser.add_argument("checksum_files", nargs=argparse.REMAINDER)

args = parser.parse_args()

if args.is_dict and args.is_list:
    print("Checksum file cannot be list AND dict", file=sys.stderr)
    parser.print_usage(file=sys.stderr)
    sys.exit(1)

if not len(args.checksum_files):
    print("At least one checksum file required", file=sys.stderr)
    parser.print_usage(file=sys.stderr)
    sys.exit(1)


try:
    seamless.delegate(raise_exceptions=True)
except AssistantConnectionError:
    seamless.delegate(level=1, force_database=True)

################################################################

checksum_list = []

if args.is_dict or args.is_list:
    checksums = json.load(open(args.checksum_files[0]))
    for path in args.checksum_files[1:]:
        curr_checksums = json.load(open(path))
        if args.is_list:
            checksums += curr_checksums
        else:
            checksums.update(curr_checksums)
    if args.is_list:
        checksum_list = checksums.copy()
    else:
        checksum_list = list(checksums.values())
else:
    checksum_mapping = {}
    paths = [path.rstrip(os.sep) for path in args.checksum_files]
    paths2 = []

    for path in paths:
        if path.endswith(".CHECKSUM"):
            checksum_file = path
            path2 = os.path.splitext(path)[0]
        else:
            checksum_file = path + ".CHECKSUM"
            path2 = path
        if os.path.exists(checksum_file) or path.endswith(".CHECKSUM"):
            checksum = read_checksum_file(checksum_file)
            if checksum is None:
                err(f"File '{checksum_file}' does not contain a checksum")
            checksum = Checksum(checksum).hex()
        else:
            try:
                checksum = Checksum(path).hex()
            except ValueError:
                err(f"{path} is not an existing file, nor a valid checksum")
        checksum_list.append(checksum)
        paths2.append(path2)
        checksum_mapping[path2] = checksum

buffer_sizes = {}
for checksum in checksum_list:
    buffer_size = ""
    buffer_info = database.get_buffer_info(checksum)
    if buffer_info is not None:
        length = buffer_info.get("length")
        if length:
            if args.human_readable:
                buffer_size = bytes2human(length).replace(" ", "")
            else:
                buffer_size = str(length)
            buffer_size = " " + buffer_size
    buffer_sizes[checksum] = buffer_size

if args.is_dict:
    for k, checksum in checksums.items():
        buffer_size = buffer_sizes[checksum]
        print(f"{k}{buffer_size}")
elif args.is_list:
    for checksum in checksums:
        buffer_size = buffer_sizes[checksum]
        print(f"{checksum}{buffer_size}")
else:
    for path2 in paths2:
        checksum = checksum_mapping[path2]
        buffer_size = buffer_sizes[checksum]
        print(f"{path2} {checksum}{buffer_size}")
