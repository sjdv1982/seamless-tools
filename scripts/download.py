#!/usr/bin/env -S python3 -u

import shutil
import sys, os
import json

os.environ["__SEAMLESS_FRUGAL"] = "1"

import seamless
from seamless import calculate_checksum
from seamless.config import AssistantConnectionError
from seamless.cmd.bytes2human import human2bytes
from seamless.highlevel import Checksum

from seamless.core.cache.buffer_cache import buffer_cache
from seamless.cmd.message import message as msg, message_and_exit as err
from seamless.cmd.file_load import (
    strip_textdata,
    read_checksum_file,
)
from seamless.cmd.download import download
from seamless.highlevel import Checksum

import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "-m",
    "-mv",
    "--move",
    dest="move",
    help="""After successful upload, delete the original files and directories""",
    action="store_true",
)

parser.add_argument(
    "-y",
    "--yes",
    dest="auto_confirm",
    help="""Sets any confirmation values to 'yes' automatically. Users will not be asked to confirm any file download.
Downloads will happen without confirmation for up to 2000 files and up to 500 MB in total.
These thresholds can be controlled by the environment variables:
SEAMLESS_MAX_DOWNLOAD_FILES, SEAMLESS_MAX_DOWNLOAD_SIZE.""",
    action="store_const",
    const="yes",
)

parser.add_argument(
    "-n",
    "--no",
    dest="auto_confirm",
    help="""Sets any confirmation values to 'no' automatically. Users will not be asked to confirm any file download.
Downloads will happen without confirmation for up to 2000 files and up to 500 MB in total.
These thresholds can be controlled by the environment variables:
SEAMLESS_MAX_DOWNLOAD_FILES, SEAMLESS_MAX_DOWNLOAD_SIZE.""",
    action="store_const",
    const="no",
)

parser.add_argument("files_and_directories", nargs=argparse.REMAINDER)

args = parser.parse_args()

max_download_files = os.environ.get("SEAMLESS_MAX_DOWNLOAD_FILES", "2000")
max_download_files = int(max_download_files)
max_download_size = os.environ.get("SEAMLESS_MAX_DOWNLOAD_SIZE", "500 MB")
max_download_size = human2bytes(max_download_size)

try:
    seamless.delegate()
except AssistantConnectionError:
    seamless.delegate(level=1)

################################################################

to_download = {}
directories = []
files = []
paths = [path.rstrip(os.sep) for path in args.files_and_directories]
index_checksums = {}
for path in paths:
    if not path.endswith(".INDEX"):
        if path.endswith(".CHECKSUM"):
            path2 = os.path.splitext(path)[0] + ".INDEX"
        else:
            path2 = path + ".INDEX"
        if os.path.exists(path2):
            path = path2
    if path.endswith(".INDEX"):
        dirname = os.path.splitext(path)[0]
        directories.append(dirname)
        if not os.path.exists(path):
            msg(0, f"Cannot read index file '{path}'")
            continue
        with open(path) as f:
            data = f.read()
        data = strip_textdata(data)
        index_buffer = data.encode() + b'\n'
        if not len(index_buffer.strip(b'\n')):
            checksum_file = os.path.splitext(path)[0] + ".CHECKSUM"
            if not os.path.exists(checksum_file):
                err(f"Index file '{path}' is empty, {checksum_file} does not exist")
            index_checksum = read_checksum_file(checksum_file)
            index_checksum = Checksum(index_checksum)
            if index_checksum is None:
                err(
                    f"Index file '{path}' is empty, {checksum_file} does not contain a checksum"
                )
            msg(1, f"Index file '{path}' is empty, downloading from checksum")
            index_buffer = buffer_cache.get_buffer(index_checksum.bytes())
            if index_buffer is None:
                err(
                    f"Index file '{path}' is empty, cannot download checksum in {checksum_file}, CacheMissError"
                )
            else:
                err_msg = f"Index file '{path}' is empty, but {checksum_file} does not contain the checksum of a valid directory index"
        else:
            index_checksum = Checksum(calculate_checksum(index_buffer))
            err_msg = f"File '{path}' is not a valid index file"

        has_err = False
        try:
            index_data = json.loads(index_buffer.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            has_err = True
        if not has_err:
            if not isinstance(index_data, dict):
                has_err = True
            else:
                for k, cs in index_data.items():
                    try:
                        cs2 = Checksum(cs)
                        assert cs2.hex() is not None
                    except Exception:
                        has_err = True
                        break
        if has_err:
            err(err_msg)
        else:
            for k, cs in index_data.items():
                kk = os.path.join(dirname, k)
                to_download[kk] = cs
        index_checksums[dirname] = index_checksum.hex()
        continue
    if path.endswith(".CHECKSUM"):
        path = os.path.splitext(path)[0]
    checksum_file = path + ".CHECKSUM"
    checksum = read_checksum_file(checksum_file)
    checksum = Checksum(checksum)
    if checksum is None:
        err(
            f"File '{checksum_file}' does not contain a checksum"
        )
    to_download[path] = checksum.hex()
    files.append(path)



################################################################

for directory in directories:
    if os.path.exists(directory):
        shutil.rmtree(directory)

newdirs = {os.path.dirname(k) for k in to_download}
for directory in directories:
    newdirs.add(directory)
for newdir in newdirs:
    if len(newdir):
        os.makedirs(os.path.join(newdir), exist_ok=True)

################################################################

download(
    files,
    directories,
    checksum_dict=to_download,
    index_checksums=index_checksums,
    max_download_size=max_download_size,
    max_download_files=max_download_files,
    auto_confirm=args.auto_confirm,
)
