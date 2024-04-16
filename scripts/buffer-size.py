#!/usr/bin/env -S python3 -u

# TODO: document

import os

os.environ["__SEAMLESS_FRUGAL"] = "1"

import seamless
from seamless import parse_checksum
from seamless.config import database, AssistantConnectionError
from seamless.cmd.bytes2human import bytes2human
from seamless.highlevel import Checksum

from seamless.cmd.message import message_and_exit as err
from seamless.cmd.file_load import (
    read_checksum_file
)

import argparse

parser = argparse.ArgumentParser()

parser.add_argument(
    "-c",
    "--checksums",
    dest="checksums",
    help='Force interpretation of arguments as checksums, rather than as files containing checksums',
    action="store_true"
)
parser.add_argument(
    "-H",
    "--human-readable",
    dest="human_readable",
    help='Print sizes in human readable format (e.g. 1kB)',
    action="store_true"
)

parser.add_argument("files_and_directories", nargs=argparse.REMAINDER)

args = parser.parse_args()

try:
    seamless.delegate(raise_exceptions=True)
except AssistantConnectionError:
    seamless.delegate(level=1, force_database=True)

################################################################

checksum_list = []
if args.checksums:
    for cs in args.files_and_directories:
        try:
            checksum = Checksum(cs).hex()
        except ValueError:
            err(f"{cs} is not a valid checksum")
        checksum_list.append(checksum)
else:
    paths = [path.rstrip(os.sep) for path in args.files_and_directories]
    for path in paths:        
        if path.endswith(".CHECKSUM"):
            checksum_file = path
        else:
            checksum_file = path + ".CHECKSUM"
        if not args.checksums and (os.path.exists(checksum_file) or path.endswith(".CHECKSUM")):
            checksum = read_checksum_file(checksum_file)
            if checksum is None:
                err(
                    f"File '{checksum_file}' does not contain a checksum"
                )
            checksum = Checksum(checksum).hex()
        else:
            try:
                checksum = Checksum(path).hex()
            except ValueError:
                err(f"{path} is not an existing file, nor a valid checksum")
        checksum_list.append(checksum)

for checksum in checksum_list:
    buffer_size = ""
    buffer_info = database.get_buffer_info(checksum)
    if buffer_info is not None:
        length = buffer_info.get("length")
        if length:
            if args.human_readable:
                buffer_size = bytes2human(length).replace(" ","")
            else:
                buffer_size = str(length)
            buffer_size = " " + buffer_size
    print(f"{checksum}{buffer_size}")