"""
Launches a Dask scheduler to be used with Seamless by setting up a SlurmCluster.

It is recommended to use this with seamless-dask-wrapper

See local.py for more details about starting Dask in a Seamless-compatible manner.

All Dask jobs will be started inside an environment SEAMLESS_DASK_CONDA_ENVIRONMENT.
For slurmcluster.py, dask-jobqueue must have been installed

Worker ports will be opened between RANDOM_PORT_START and RANDOM_PORT_END

Resource requirements are currently hardcoded. For a new project, you are 
recommended to clone and modify this script and wrap-slurmcluster.sh.
See the documentation of the dask-jobqueue

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

# Check that port range is defined
os.environ["RANDOM_PORT_START"]
os.environ["RANDOM_PORT_END"]

# Check that conda works
os.environ["CONDA_PREFIX"]
os.environ["SEAMLESS_DASK_CONDA_ENVIRONMENT"]

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="0.0.0.0", required=False)
parser.add_argument("--port", default=0, type=int, required=False)
args = parser.parse_args()

from dask_jobqueue import SLURMCluster

scheduler_kwargs={"host":args.host}
if args.port > 0:
    scheduler_kwargs["port"] = args.port

conda_shlvl = int(os.environ["CONDA_SHLVL"])
if conda_shlvl == 1:
    CONDA_PREFIX = os.environ["CONDA_PREFIX"]
else:
    CONDA_PREFIX = os.environ["CONDA_PREFIX_1"]

exported_vars = [
    "SEAMLESS_DASK_CONDA_ENVIRONMENT",
    "SEAMLESS_DATABASE_IP",
    "SEAMLESS_DATABASE_PORT",
    "SEAMLESS_READ_BUFFER_SERVERS",
    "SEAMLESS_WRITE_BUFFER_SERVER"
]
for var in exported_vars:
    print("{}={}".format(var, os.environ[var]))
print()

cluster = SLURMCluster(
    #queue='regular',
    
    # processes should be 1, otherwise you get trouble
    processes=1, 
    
    # The scheduler will send this many tasks to each job
    cores=8,
    memory="16 GB",
    python="python",

    # TODO: devise a way to set seamless.ncores equal to SLURMCluster.cores
    job_script_prologue=[
        "#SBATCH --export={}".format(",".join(exported_vars)),
        "set -u -e",
        "source {}/etc/profile.d/conda.sh".format(CONDA_PREFIX),        
        "conda info --envs",    
        "conda activate $SEAMLESS_DASK_CONDA_ENVIRONMENT",
        "export DASK_DISTRIBUTED__WORKER__MULTIPROCESSING_METHOD=fork",
        "export DASK_DISTRIBUTED__WORKER__DAEMON=False",
    ],

    worker_extra_args=[
        "--worker-port={}:{}".format(
            os.environ["RANDOM_PORT_START"],
            os.environ["RANDOM_PORT_END"]
        ),
        "--nanny-port={}:{}".format(
            os.environ["RANDOM_PORT_START"],
            os.environ["RANDOM_PORT_END"]
        )
    ],
    scheduler_options=scheduler_kwargs
)

cluster.adapt(minimum_jobs=0, maximum_jobs=50)

print(cluster.job_script())

print("Dask scheduler address:")
print(cluster.scheduler_address)
sys.stdout.flush()

if not sys.__stdin__.isatty():
    import time
    time.sleep(99999999)