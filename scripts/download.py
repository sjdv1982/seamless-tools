#!/usr/bin/env -S python3 -u

# TODO: document
# in particular, point out that:
# - .INDEX file may contain comments and whitespace
#    and if empty of anything else, 
#    the index is built from the .CHECKSUM file.

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


parser.add_argument(
    "-o",
    "--output",
    dest="outputs",
    help='Explicitly specify output file or directory. Can be repeated in case of multiple downloads',
    action="append",
    default=[],
)

parser.add_argument(
    "--stdout",
    help='Print all downloaded buffers to standard output',
    action="store_true",
    default=False
)

parser.add_argument(
    "--directory",
    help='Treat all raw checksum arguments as checksums to directory index buffers',
    action="store_true",
    default=False
)

parser.add_argument(
    "--index",
    dest="index_only",
    help='For directories (deep buffers), only download the index, and write one checksum file per buffer.',
    action="store_true",
    default=False
)

parser.add_argument("files_directories_and_checksums", nargs=argparse.REMAINDER)

args = parser.parse_args()

for path in args.files_directories_and_checksums:
    if path.startswith("-"):
        err("Options must be specified before files/directories")

max_download_files = os.environ.get("SEAMLESS_MAX_DOWNLOAD_FILES", "2000")
max_download_files = int(max_download_files)
max_download_size = os.environ.get("SEAMLESS_MAX_DOWNLOAD_SIZE", "500 MB")
max_download_size = human2bytes(max_download_size)

try:
    seamless.delegate(raise_exceptions=True)
except AssistantConnectionError:
    try:
        seamless.delegate(level=3, raise_exceptions=True)
    except Exception:
        has_err = seamless.delegate(level=2)
        if has_err:
            exit(1)

################################################################

to_download = {}
directories = []
files = []
index_checksums = {}
paths = [path.rstrip(os.sep) for path in args.files_directories_and_checksums]
for pathnr, path in enumerate(paths):
    parsed_checksum = None
    if not path.endswith(".INDEX"):
        if path.endswith(".CHECKSUM"):
            path2 = os.path.splitext(path)[0] + ".INDEX"
        else:
            try:
                parsed_checksum = Checksum(path)
            except ValueError:
                pass
            path2 = path + ".INDEX"
        if os.path.exists(path2) or (args.index_only and os.path.exists(os.path.splitext(path2)[0] + ".CHECKSUM")):
            path = path2
        elif args.directory and parsed_checksum:
            path += ".INDEX"

    if path.endswith(".INDEX"):
        dirname = os.path.splitext(path)[0]
        if pathnr < len(args.outputs):
            dirname = args.outputs[pathnr]

        directories.append(dirname)
        if parsed_checksum:
            index_checksum = parsed_checksum
            index_buffer = None
        else:
            if not os.path.exists(path):
                index_buffer = None
                index_err = f"Cannot read index file '{path}'"
            else:
                with open(path) as f:
                    data = f.read()
                data = strip_textdata(data)
                index_buffer = data.encode() + b'\n'
                if not index_buffer.strip(b'\n'):
                    index_buffer = None
                    index_err = f"Index file '{path}' is empty"
        if index_buffer is None:
            checksum_file = os.path.splitext(path)[0] + ".CHECKSUM"
            if not (parsed_checksum or args.directory) and not os.path.exists(checksum_file):
                err(f"{index_err}, {checksum_file} does not exist")
            if index_checksum is None:
                index_checksum = read_checksum_file(checksum_file)
            if index_checksum is None:
                err(
                    f"{index_err}, {checksum_file} does not contain a checksum"
                )
            index_checksum = Checksum(index_checksum)
            if not (args.index_only or args.directory):
                msg(0, f"{index_err}, downloading from checksum ...")
            index_buffer = buffer_cache.get_buffer(index_checksum.bytes())
            if index_buffer is None:
                if parsed_checksum:
                    err(f"Cannot download index buffer for {parsed_checksum}")
                err(
                    f"{index_err}, cannot download checksum in {checksum_file}, CacheMissError"
                )
            else:
                if not (args.index_only or args.directory):
                    msg(0, "... success")
                if parsed_checksum:
                    maybe_err_msg = f"Buffer with checksum {parsed_checksum} is not a valid index buffer"
                else:
                    with open(path, "wb") as f:
                        f.write(index_buffer)                
                    maybe_err_msg = f"{index_err}, but {checksum_file} does not contain the checksum of a valid directory index"

        else:
            index_checksum = Checksum(calculate_checksum(index_buffer))
            maybe_err_msg = f"File '{path}' is not a valid index file"

        if dirname != os.path.splitext(path)[0]:
            if index_buffer is not None:
                with open(dirname + ".INDEX", "wb") as f:
                    f.write(index_buffer)
            if args.index_only:
                with open(dirname + ".CHECKSUM", "w") as f:
                    f.write(index_checksum.hex() + "\n")

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
            err(maybe_err_msg)
        else:
            for k, cs in index_data.items():
                kk = os.path.join(dirname, k)
                to_download[kk] = cs
        index_checksums[dirname] = index_checksum.hex()
        continue    
    
    checksum = None
    if path.endswith(".CHECKSUM"):
        path = os.path.splitext(path)[0]
    elif parsed_checksum:
        checksum = parsed_checksum
    
    if checksum is None:
        checksum_file = path + ".CHECKSUM"
        checksum = read_checksum_file(checksum_file)
        if checksum is None:
            err(
                f"File '{checksum_file}' does not contain a checksum"
            )
        checksum = Checksum(checksum)
    
    if pathnr < len(args.outputs):
        path = args.outputs[pathnr]
    to_download[path] = checksum.hex()
    files.append(path)


################################################################

if not args.index_only:
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

if args.index_only:
    for path, checksum in to_download.items():
        with open(path + ".CHECKSUM", "w") as f:
            f.write(checksum + "\n")
elif args.stdout:
    if len(directories):
        err("Cannot download and print directory to stdout")
    if len(files) > 1:
        err("Cannot download and print multiple files to stdout")
    else:
        cs = to_download[files[0]]
        file_buffer = buffer_cache.get_buffer(bytes.fromhex(cs))
        sys.stdout.buffer.write(file_buffer)
else:
    download(
        files,
        directories,
        checksum_dict=to_download,
        index_checksums=index_checksums,
        max_download_size=max_download_size,
        max_download_files=max_download_files,
        auto_confirm=args.auto_confirm
    )
