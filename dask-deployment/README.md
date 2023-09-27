There are two methods to start up a Seamless Dask deployment

In both cases, first build a Seamless Dask conda environment,
using build-environment*.sh

## Local method

- Start `seamless-delegate none` . This will start up the database and hashserver
- Activate the Seamless Dask conda environment
- `source seamless-fill-environment-variables`, then launch local.py and keep it alive. Note the Dask scheduler address.
- Do `export DASK_SCHEDULER_ADDRESS=...`  and then `seamless-delegate mini-dask-assistant` (or `mini-dask-assistant-devel`)
- Start `seamless-bash` or import seamless directly from conda, with `source seamless-fill-environment-variables`.

## Remote method

- Log in (or launch a batch shell script) on a remote machine.
- There, activate the Seamless Dask conda environment
- Run `./one-node.sh $RANDOM_PORT_START $RANDOM_PORT_END`, specifying a random port range for the hashserver, the database, and the Dask scheduler. You may add a hostname too. Keep this alive.
(There may be alternatives to `one-node.sh` that dynamically launch new jobs on the cluster).
- Copy the variables between ####
- In a new local terminal, paste the variables.
- In that terminal, start `seamless-delegate-remote mini-dask-assistant` (or `mini-dask-assistant-devel`)
- Then, start `seamless-bash` or import seamless directly from conda
