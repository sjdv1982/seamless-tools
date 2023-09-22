import argparse
import json
import asyncio
parser = argparse.ArgumentParser()
parser.add_argument("checksum")
parser.add_argument("--ncores",type=int,default=None)
parser.add_argument("--direct-print", dest="direct_print", action="store_true")
parser.add_argument(
    "--verbose",
    help="Verbose mode, setting the Seamless logger to INFO",
    action="store_true"
)

parser.add_argument(
    "--debug",
    help="Debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
    action="store_true"
)

parser.add_argument(
    "--fingertip",
    help="Make sure that the result is available as buffer, not just as checksum.",
    action="store_true"
)

parser.add_argument(
    "--dunder",
    help="""Dunder file.
Contains additional information for the transformation, in particular __meta__ and __env__.
Note that __env__ must be specified as a checksum, the buffer of which must be available"""
)

parser.add_argument(
    "--global_info",
    help="""Global info file.
Contains information about the hardware and system, as generated
by seamless.core.transformation.get_global_info.
Providing this information saves 5-10 seconds."""
)

args = parser.parse_args()

import seamless
from seamless import Checksum

checksum = Checksum(args.checksum)

if args.debug:
    asyncio.get_event_loop().set_debug(True)
    import logging
    logging.basicConfig()
    logging.getLogger("seamless").setLevel(logging.DEBUG)
elif args.verbose:
    import logging
    logging.basicConfig()
    logging.getLogger("seamless").setLevel(logging.INFO)

seamless.delegate(level=3)

if args.ncores is not None and args.ncores > 0:
    seamless.set_ncores(args.ncores)

if args.direct_print:
    import seamless.core.execute
    seamless.core.execute.DIRECT_PRINT = True

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

from seamless.core.transformation import get_global_info, execution_metadata0
get_global_info(global_info)
execution_metadata0["Executor"] = "run-transformation"

result = seamless.run_transformation(checksum.bytes(), fingertip=fingertip, tf_dunder=dunder)

if result is not None:
    result = Checksum(result).hex()
print(result)
