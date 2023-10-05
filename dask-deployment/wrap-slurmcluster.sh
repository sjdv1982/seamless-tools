#!/bin/bash
# a wrapper around slurmcluster.py to be used with seamless-dask-wrapper
set -u -e

currdir=`python3 -c 'import os,sys;print(os.path.dirname(os.path.realpath(sys.argv[1])))' $0`

# Does not work (asyncio trouble)
#ipython3 -i $currdir/slurmcluster.py -- --host $SEAMLESS_ASSISTANT_HOST --port $DASK_SCHEDULER_PORT

python3 -i $currdir/slurmcluster.py --host $SEAMLESS_ASSISTANT_HOST --port $DASK_SCHEDULER_PORT