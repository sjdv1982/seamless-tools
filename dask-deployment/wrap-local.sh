#!/bin/bash
# a wrapper around local.py to be used with seamless-dask-wrapper
set -u -e

currdir=`python3 -c 'import os,sys;print(os.path.dirname(os.path.realpath(sys.argv[1])))' $0`
python3 -i $currdir/local.py --host $SEAMLESS_ASSISTANT_HOST --port $DASK_SCHEDULER_PORT