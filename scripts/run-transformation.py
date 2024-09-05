import argparse
import json
import asyncio
import sys
import os

parser = argparse.ArgumentParser()
parser.add_argument("checksum", help="Seamless checksum or checksum file")
parser.add_argument("--ncores", type=int, default=None)
parser.add_argument("--direct-print", dest="direct_print", action="store_true")
parser.add_argument(
    "--verbose",
    help="Verbose mode, setting the Seamless logger to INFO",
    action="store_true",
)

parser.add_argument(
    "--debug",
    help="Debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
    action="store_true",
)

parser.add_argument(
    "--delegate",
    help="Delegate the transformation task to the assistant",
    action="store_true",
)

parser.add_argument(
    "--fingertip",
    help="""Make sure that the result is available as buffer, not just as checksum.
NOTE: if --scratch is also present, run-transformation will return the result buffer 
instead of the result checksum""",
    action="store_true",
)

parser.add_argument(
    "--scratch",
    help="""Don't write the computed result buffer.
NOTE: if --fingertip is also present, run-transformation will return the result buffer 
instead of the result checksum""",
    default=False,
    action="store_true",
)

parser.add_argument(
    "--output",
    help="Output file (default: stdout)",
)

parser.add_argument(
    "--dunder",
    help="""Dunder file.
Contains additional information for the transformation, in particular __meta__ and __env__.
Note that __env__ must be specified as a checksum, the buffer of which must be available""",
)

parser.add_argument(
    "--undo", help="Undo this transformation", action="store_true", default=False
)

parser.add_argument(
    "--global_info",
    "--global-info",
    help="""Global info file.
Contains information about the hardware and system, as generated
by seamless.workflow.core.transformation.get_global_info or seamless-get-global-info.
In the absence of a delegation assistant, providing this information
saves 5-10 seconds.""",
)

args = parser.parse_args()

import seamless
from seamless import Checksum, CacheMissError
from seamless.workflow.core.direct.run import (
    get_dummy_manager,
    fingertip as do_fingertip,
)
from seamless.config import database
from seamless.cmd.file_load import read_checksum_file

if args.checksum.endswith(".CHECKSUM") and os.path.exists(args.checksum):
    checksum = Checksum(read_checksum_file(args.checksum))
else:
    checksum = Checksum(args.checksum)

import logging

logging.basicConfig()
if args.debug:
    asyncio.get_event_loop().set_debug(True)
    logging.getLogger("seamless").setLevel(logging.DEBUG)
elif args.verbose:
    logging.getLogger("seamless").setLevel(logging.INFO)
else:
    logging.getLogger("seamless").setLevel(logging.ERROR)

if args.delegate:
    seamless.delegate()
else:
    seamless.delegate(level=3)

if args.ncores is not None and args.ncores > 0:
    seamless.set_ncores(args.ncores)

if args.direct_print:
    import seamless.workflow.core.execute

    seamless.workflow.core.execute.DIRECT_PRINT = True

dunder = None
if args.dunder:
    with open(args.dunder) as dunderfile:
        dunder = json.load(dunderfile)

global_info = None
if args.global_info:
    with open(args.global_info) as global_info_file:
        global_info = json.load(global_info_file)

fingertip = False
if args.fingertip:
    fingertip = True

scratch = False
if args.scratch:
    scratch = True

if fingertip and scratch:
    if not args.output:
        raise Exception(
            "With --fingertip and --scratch, the output is a buffer, and --output is mandatory"
        )

if not fingertip and not args.output:
    result = database.get_transformation_result(checksum.bytes())
    if result is not None:
        if args.undo:
            status, response = database.contest(
                checksum.bytes(), Checksum(result).bytes()
            )
            if status == 200:
                print("Transformation undone", file=sys.stderr)
                exit(0)
            else:
                print("Transformation unknown", file=sys.stderr)
                exit(1)
        result = Checksum(result).hex()
        print(result)
        exit(0)
    else:
        if args.undo:
            print("Transformation unknown", file=sys.stderr)
            exit(1)

# To hold on fingertipped buffers for longer
from seamless.workflow.core.cache.buffer_cache import buffer_cache

buffer_cache.LIFETIME_TEMP = 600.0
buffer_cache.LIFETIME_TEMP_SMALL = 1200.0

from seamless.workflow.core.transformation import get_global_info, execution_metadata0

if global_info is not None:
    get_global_info(global_info)
execution_metadata0["Executor"] = "run-transformation"

if not args.delegate:
    transformation_buffer = do_fingertip(checksum.bytes())
    if transformation_buffer is None:
        raise CacheMissError(checksum)
    transformation = json.loads(transformation_buffer.decode())
    lang = transformation.get("__language__")
    if not lang.startswith("<"):
        for k, v in transformation.items():
            if not k.startswith("__"):
                _, _, pin_checksum = v
                do_fingertip(pin_checksum)

manager = get_dummy_manager()
result = seamless.run_transformation(
    checksum.bytes(),
    fingertip=fingertip,
    tf_dunder=dunder,
    scratch=scratch,
    manager=manager,
)
if result is not None:
    if fingertip and scratch:
        result_buffer = do_fingertip(result)
        if result_buffer is None:
            raise CacheMissError(result)
        with open(args.output, "wb") as f:
            f.write(result_buffer)
    else:
        result = Checksum(result).hex()
        if args.output:
            with open(args.output, "w") as f:
                print(result, file=f)
        else:
            print(result)
else:
    if args.undo:
        print("Transformation unknown", file=sys.stderr)
    else:
        print(f"Transformation failed", file=sys.stderr)
    exit(1)
