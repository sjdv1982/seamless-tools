import argparse
import json
import asyncio
import sys
import os
parser = argparse.ArgumentParser()
parser.add_argument("checksum_or_checksum_file")


args = parser.parse_args()

import seamless
seamless.delegate(level=3)

from seamless.core.direct.run import fingertip
from seamless import Checksum, CacheMissError
from seamless.cmd.file_load import read_checksum_file
from seamless.cmd.message import message as msg, message_and_exit as err


try:
    checksum = Checksum(args.checksum_or_checksum_file)
except Exception:
    checksum_file = args.checksum_or_checksum_file
    if not os.path.exists(checksum_file):
        print(f"{checksum_file} is neither a valid checksum nor an existing file", file=sys.stderr)
        exit(1)
    checksum = read_checksum_file(checksum_file)
    if checksum is None:
        err(
            f"File '{checksum_file}' does not contain a checksum"
        )
    checksum = Checksum(checksum)

try:
    result_buffer = fingertip(checksum.bytes())
except CacheMissError:
    result_buffer = None
if result_buffer is None:
    print("Fingertipping failed", file=sys.stderr)
    exit(1)
sys.stdout.flush()
sys.stdout.buffer.write(result_buffer)