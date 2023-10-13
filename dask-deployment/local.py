"""
Launches a Dask scheduler to be used with Seamless by setting up a LocalCluster.

General criteria for starting Dask in a Seamless-compatible manner:

- The current process contains the scheduler, it must be kept alive.
- The scheduler address must be printed out so that it can be used 
  by the Seamless assistant or mini-dask assistant. 
  Alternatively, the scheduler port may be pre-defined using --port,
  so that the scheduler address is already known.
- If the deployment is *fully local* (i.e. on the same machine as the
  database AND the buffer server AND the client script that will use Seamless)
  then it is sufficient to do "export DASK_SCHEDULER_ADDRESS=..." 
  using the address printed above, 
  and then run "seamless-delegate mini-dask-assistant".
- If the deployment is at least partially *remote*, then Seamless delegation 
  must be setup correctly, both for the current deployment script and 
  for the client script. 
  The Dask scheduler must also listen at the appropriate hosts/IP address(es).
- It must be ensured that all Dask workers are started in an environment
  that contains Seamless and all other packages that they may need.
  Note that Dask workers are normally launched in identical environments.
- The Dask workers must have proper multiprocessing flags: 
  the method must be "fork", and "daemon" must be False.
  These must be set after importing Dask, but before importing
  Dask.distributed.
"""

import dask
import sys
import os
import argparse

# Check that delegation works
os.environ["SEAMLESS_DATABASE_IP"]
os.environ["SEAMLESS_DATABASE_PORT"]
os.environ["SEAMLESS_READ_BUFFER_SERVERS"]
os.environ["SEAMLESS_WRITE_BUFFER_SERVER"]

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", required=False)
parser.add_argument("--port", default=0, type=int, required=False)
parser.add_argument("--ncores", type=int, required=False)
args = parser.parse_args()

dask.config.set({'distributed.worker.multiprocessing-method': 'fork'})
dask.config.set({'distributed.worker.daemon': False})

# This import must happen AFTER dask.config!!!
from dask.distributed import LocalCluster
from dask.system import CPU_COUNT

scheduler_kwargs={"host":args.host}
if args.port > 0:
    scheduler_kwargs["port"] = args.port

ncores = args.ncores
if ncores is None:
    ncores = CPU_COUNT
dask.config.set({"distributed.worker.resources.ncores": ncores})
cluster = LocalCluster(
    n_workers=1,
    threads_per_worker=ncores,
    scheduler_kwargs=scheduler_kwargs,
    resources = {"ncores": ncores},
)

print("Dask scheduler address:")
print(cluster.scheduler_address)
sys.stdout.flush()

def is_interactive():
    if sys.flags.interactive:
        return True
    try:
        from IPython import get_ipython
        return (get_ipython() is not None)
    except ImportError:
        return False

if not is_interactive():
    print("Press Ctrl+C to stop")
    import time
    time.sleep(99999999)