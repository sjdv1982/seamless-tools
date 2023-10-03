#!/bin/bash
# a wrapper around local.py to be used with seamless-dask-wrapper
set -u -e
python3 local.py --host $SEAMLESS_ASSISTANT_HOST --port $DASK_SCHEDULER_PORT