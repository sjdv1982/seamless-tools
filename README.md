This repo contains tools related to the deployment of Seamless (https://github.com/sjdv1982/seamless).

- The seamless-cli commands, written in bash, and using the Docker command line interface.
seamless-cli is distributed as a conda package. 
Building the package requires the *seamless* conda environment to be activated.


- The Seamless scripts and tools, usually accessed via the seamless-cli. Standalone tools are the *FAIR server* and *jobless*

- The Dockerfile to build the rpbs/seamless Docker image.
  This file installs the seamless-framework conda package on top of 
  the rpbs/seamless-deps Docker image, and adds the
  scripts and tools directories from here.
  The Seamless examples and tests are also bundled.
  Command: build-docker.sh

- The Dockerfile for the rpbs/seamless-deps Docker image. 
  This installs the dependencies of Seamless on top of the Jupyter notebook+scipy Docker image.
  Solving the conda environment typically takes 5 minutes.
  Command: build-docker-seamless-deps.sh

- The Dockerfile for the seamless-devel Docker image.
  This is a version of rpbs/seamless without Seamless itself,
  where an external Seamless directory must be provided using SEAMLESS_DIR, mounted into the Docker container at runtime.
  This is used for developing and debugging Seamless.
  Command: build-docker-seamless-devel.sh

# Jobless

Jobless is an experimental workload manager for Seamless.

## Configuring Jobless

Jobless configuration needs to be done in a .yaml file.

There are several documented example configuration files in `jobless/config/*.yaml`. These configure *jobhandlers* for various kinds of transformations.

See `jobless/config/local.yaml` for a minimal example, where bash transformations and bashdocker transformations are run as local jobs.
Other .yaml files in that directory show:
- The use of a Slurm backend.
- The use of Singularity for bashdocker transformations (with Slurm)
- The use of generic transformers. These can run transformations in any language (bash, Python, compiled, ipython-bridged) with any conda environment specified. Transformations are run inside a `rpbs/seamless-minimal` Docker container, and an external location
must be provided where jobless can store Conda environments.
- The use of generic transformers plus Singularity. Instead of in a Docker container, these run inside a Singularity container.
- Generic transformers plus Singularity plus Slurm.


## Setup

***NOTE: Jobless does not run properly under Python3.10. It does run
properly under Python3.8. You are recommended to create a new conda environment for Jobless using `conda create -n jobless 'python=3.8'`***

Jobless runs without containerization. Its dependencies are in `jobless/requirements.txt`, to be installed with `pip -r`. It also requires silk and a few other dependencies, depending on which jobhandlers are being used.
Please read `jobless/requirements.txt` for further instructions.

Launch jobless with `python3 /jobless/jobless.py <config file>.yaml`

## Testing Jobless

First, delete the database and launch jobless. 

### Specific Jobless tests

These are available in `jobless/tests`. They use the Transformer.docker_image values "ubuntu", "rpbs/seamless" and "rpbs/autodock". Make sure that these are available as Docker or Singularity images in the place where the jobs will be run.

Launch a shell in a Seamless container with `seamless-bash`

Run the tests `bash.py`, `docker_.py` and `autodock.py` with python3.
This will connect to a running Jobless instance.
See the .expected-output files in the same folder.
If the output contains instead `Local computation has been disabled for this Seamless instance` or `Environment power cannot be granted: 'docker'`, then the test has failed, because a connection to Jobless
could not be made. `CacheMissError` indicates a failure in connecting
to the Seamless database.

The above tests are for bash/bashdocker transformations and will work for all of the config files in `/jobless/config`. In addition, there are the following tests that require a config file with a generic jobhandler:

- `simple.py`: simple Python transformer.

- `parse-pdb.py`: a Python transformer with a conda environment.

- `compiled.py`: a C++ transformer.

### Testing Jobless in the general case

You can use Seamless's generic `seamless-serve-graph` command together with jobless, for any Seamless graph saved with `ctx.save_graph()` + `ctx.save_zip()` . For example, the "share-pdb" graph in `seamless-tests/highlevel` (bundled with the Seamless Docker image) requires only bash transformers:
```
graph_dir=/home/jovyan/seamless-tests/highlevel
seamless-add-zip $graph_dir/share-pdb.zip
seamless-serve-graph $graph_dir/share-pdb.seamless --database --communion --ncores 0
```
Then, open [http://localhost:5813/ctx/index.html]. 
Use `seamless-serve-graph-interactive` to get an IPython shell instead.

# FAIR server

STUB