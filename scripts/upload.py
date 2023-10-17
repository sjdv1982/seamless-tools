#!/usr/bin/env -S python3 -u

from concurrent.futures import ThreadPoolExecutor
import sys, os
import shutil

os.environ["__SEAMLESS_FRUGAL"] = "1"
import seamless
from seamless.config import AssistantConnectionError
from seamless.cmd.message import set_verbosity, message as msg, message_and_exit as err
from seamless.cmd.file_load import files_to_checksums
from seamless.cmd.bytes2human import bytes2human, human2bytes
from seamless.cmd.exceptions import SeamlessSystemExit
from seamless.highlevel import Checksum
from seamless.core.protocol.json import json_dumps
from seamless import calculate_checksum

import argparse
parser = argparse.ArgumentParser()

parser.add_argument(
    "-v",
    dest="verbosity",
    help="""Verbose mode.
Multiple -v options increase the verbosity. The maximum is 3""",
    action="count",
    default=0,
)
parser.add_argument(
    "-q", dest="verbosity", help="Quiet mode", action="store_const", const=-1
)

parser.add_argument(
    "-m", "-mv", "--move",
    dest="move",
    help="""After successful upload, delete the original files and directories""",
    action="store_true",
)

parser.add_argument(
    "-y",
    "--yes",
    dest="auto_confirm",
    help="""Sets any confirmation values to 'yes' automatically. Users will not be asked to confirm any file upload or download.
Uploads will happen without confirmation for up to 400 files and up to 100 MB in total.
Downloads will happen without confirmation for up to 2000 files and up to 500 MB in total.
These thresholds can be controlled by the environment variables:
SEAMLESS_MAX_UPLOAD_FILES, SEAMLESS_MAX_UPLOAD_SIZE, SEAMLESS_MAX_DOWNLOAD_FILES, SEAMLESS_MAX_DOWNLOAD_SIZE.""",
    action="store_const",
    const="yes",
)

parser.add_argument(
    "-n",
    "--no",
    dest="auto_confirm",
    help="""Sets any confirmation values to 'no' automatically. Users will not be asked to confirm any file upload or download.
Uploads will happen without confirmation for up to 400 files and up to 100 MB in total.
Downloads will happen without confirmation for up to 2000 files and up to 500 MB in total.
These thresholds can be controlled by the environment variables:
SEAMLESS_MAX_UPLOAD_FILES, SEAMLESS_MAX_UPLOAD_SIZE, SEAMLESS_MAX_DOWNLOAD_FILES, SEAMLESS_MAX_DOWNLOAD_SIZE.""",
    action="store_const",
    const="no",
)

parser.add_argument("files_and_directories", nargs=argparse.REMAINDER)

args = parser.parse_args()


max_upload_files = os.environ.get("SEAMLESS_MAX_UPLOAD_FILES", "400")
max_upload_files = int(max_upload_files)
max_upload_size = os.environ.get("SEAMLESS_MAX_UPLOAD_SIZE", "100 MB")
max_upload_size = human2bytes(max_upload_size)

try:
    seamless.delegate()
except AssistantConnectionError:
    seamless.delegate(level=2)

paths = [path.rstrip(os.sep) for path in args.files_and_directories]
directories = [path for path in paths if os.path.isdir(path)]
    
try:
    file_checksum_dict, _, directory_indices = files_to_checksums(
        paths,        
        max_upload_size=max_upload_size,
        max_upload_files=max_upload_files,
        directories=directories,
        direct_checksum_directories=None,
        auto_confirm=args.auto_confirm,
    )
except SeamlessSystemExit as exc:
    err(*exc.args)

def write_checksum(filename, file_checksum):
    file_checksum = Checksum(file_checksum)
    if file_checksum.value is None:
        return
    try:
        with open(filename + ".CHECKSUM", "w") as f:
            f.write(file_checksum.hex() + "\n")
    except Exception:
        msg(0, f"Cannot write checksum to file '{filename}.CHECKSUM'")
        return

for dirname in directories:
    index_buffer, index_checksum = directory_indices[dirname]
    try:
        with open(dirname + ".INDEX", "wb") as f:
            f.write(index_buffer)
    except Exception:
        msg(0, f"Cannot write directory index to file '{dirname}.INDEX'")
    else:
        write_checksum(dirname, index_checksum)


filenames = [path for path in paths if path not in directories]
with ThreadPoolExecutor(max_workers=100) as executor:
    executor.map(
        write_checksum, filenames, [file_checksum_dict[path] for path in filenames]
    )

if args.move:
    with ThreadPoolExecutor(max_workers=100) as executor:
        executor.map(
            shutil.rmtree, paths
        )
