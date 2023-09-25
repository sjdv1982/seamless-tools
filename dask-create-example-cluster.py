"""
Criteria for starting Dask in a Seamless-compatible manner
- The current process contains the scheduler, it must be kept alive.
- The scheduler address must be printed out so that it can be used 
  by the Seamless assistant or mini-dask assistant. 
  If it is on a remote machine, it must listen on the appropriate
  hosts/IP address(es).
- It must be ensured that all Dask workers are started in an environment
  that contains Seamless and all other packages that they may need.
  Note that Dask workers are normally launched in identical environments.
- The Dask workers must have proper multiprocessing flags: 
  the method must be "fork", and "daemon" must be False.
  These must be set after importing Dask, but before importing
  Dask.distributed.
"""

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