"""
Criteria for starting Dask in a Seamless-compatible manner
- The current process contains the scheduler, it must be kept alive.
- The scheduler address must be printed out so that it can be used 
  by the Seamless assistant or mini-dask assistant. 
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

import os

# Check that delegation works
os.environ["SEAMLESS_DATABASE_IP"]
os.environ["SEAMLESS_DATABASE_PORT"]
os.environ["SEAMLESS_READ_BUFFER_SERVERS"]
os.environ["SEAMLESS_WRITE_BUFFER_SERVER"]

import sys
import dask
dask.config.set({'distributed.worker.multiprocessing-method': 'fork'})
dask.config.set({'distributed.worker.daemon': False})

from dask.distributed import LocalCluster
cluster = LocalCluster(scheduler_kwargs={"host": "0.0.0.0"})

print(cluster.scheduler_address)
sys.stdout.flush()

import time
time.sleep(9999999)