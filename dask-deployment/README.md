# Dask deployment

There are three methods to start up a Seamless Dask deployment

In all cases, first build a Seamless Dask conda environment,
using build-environment*.sh

## Local method

- Start `seamless-delegate none` . This will start up the database and hashserver
- Activate the Seamless Dask conda environment
- `source seamless-fill-environment-variables`, then launch local.py and keep it alive. Note the Dask scheduler address.
- In a different terminal, do `export DASK_SCHEDULER_ADDRESS=...`  and then `seamless-delegate mini-dask-assistant` (or `mini-dask-assistant-devel`)
- Start `seamless-bash` or import seamless directly from conda, with `source seamless-fill-environment-variables`.

## Remote method with direct connection

This requires that the remote IP address is directly reachable from your machine.
You must define a port range, and all ports within that range must be accessible.

- Log in (or launch a batch shell script) on a remote machine.
- There, activate the Seamless Dask conda environment
- Run `./one-node.sh $RANDOM_PORT_START $RANDOM_PORT_END`, specifying a random port range for the hashserver, the database, and the Dask scheduler. You may add a hostname too. Keep this script alive.
(There may be alternatives to `one-node.sh` that dynamically launch new jobs on the cluster).
- Variables will be printed out. Copy the variable section for direct connection.
- In a new local terminal, paste the variable section.
- In that terminal, start `seamless-delegate-remote mini-dask-assistant` (or `mini-dask-assistant-devel`)
- In any local terminal, paste the variable section.
  Then, start `seamless-bash` or import seamless directly from conda. 

## Remote method with SSH tunneling

This requires that the remote IP address can be reached via SSH without login.
The remote ports are tunneled to the default local Seamless ports. Therefore,
`seamless-delegate-stop` must be called to stop any existing local delegation.

- Log in (or launch a batch shell script) on a remote machine.
- There, activate the Seamless Dask conda environment
- Run `./one-node.sh $RANDOM_PORT_START $RANDOM_PORT_END 0.0.0.0`, specifying a random port range for the hashserver, the database, and the Dask scheduler, and a hostname 0.0.0.0 that listens on all IP addresses. You may try to omit 0.0.0.0 or give a different hostname. 
Keep this script alive.
(There may be alternatives to `one-node.sh` that dynamically launch new jobs on the cluster).
- Variables will be printed out. Copy the variable section for SSH connection.
  You may need to change SEAMLESS_SSH_HOST if it is different from the entry in
  your `.ssh/config`.
- In a new local terminal, paste the variable section.
- In that terminal, start `seamless-delegate-ssh mini-dask-assistant` (or `mini-dask-assistant-devel`). Unlike the other `seamless-delegate*` scripts, the terminal will block while `seamless-delegate-ssh` is active.  
- In another local terminal, start `seamless-bash` or import seamless directly from conda. Pasting the variable section is not necessary.
