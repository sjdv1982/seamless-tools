This repo contains tools related to the distribution and deployment of Seamless (https://github.com/sjdv1982/seamless).

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

OUTDATED!

Jobless configuration needs to be done in a .yaml file.

There are several documented example configuration files in `jobless/config/*.yaml`. These configure *jobhandlers* for various kinds of transformations.

See `jobless/config/local.yaml` for a minimal example, where bash transformations and bashdocker transformations are run as local jobs.
Other .yaml files in that directory show:

- The use of a Slurm backend.
- The use of Singularity for bashdocker transformations (with Slurm)
- The use of generic transformers. These can run transformations in any language (bash, Python, compiled, ipython-bridged) with any conda environment specified. Transformations are run inside a `rpbs/seamless-minimal` Docker container, and an external location
must be provided where jobless can store conda environments.
- The use of generic transformers plus Singularity. Instead of in a Docker container, these run inside a Singularity container.
See the `seamless-cli-singularity/' subfolder for more details.
- Generic transformers plus Singularity plus Slurm.
- Generic transformers plus bare metal. Instead of a Docker or Singularity container, the transformers are executed in a cloned `seamless-baremetal` conda environment. See the `seamless-cli-baremetal/' subfolder for more details.
- Generic transformers plus bare metal plus Slurm.

## Setup

You are recommended to create a new conda environment for Jobless using `conda create -n jobless`

Jobless runs without containerization. Its dependencies are in `jobless/requirements.txt`, to be installed with `pip -r`. It also requires silk and a few other dependencies, depending on which jobhandlers are being used.
Please read `jobless/requirements.txt` for further instructions.

Launch jobless with `python3 /jobless/jobless.py <config file>.yaml`

## Testing Jobless

First, launch a database and launch jobless. You are recommended to use a fresh temporary database directory, e.g. `seamless-database /tmp/somedir` and delete it after running tests. However, with the test suite it is possible to delete only the tested data, computations and results from the database.

### Test configs

In `config/`, there are several jobless config files that you can test and/or adapt to your needs. They are briefly explained below. More information on jobless config options is in the Seamless documentation, and in the config files themselves.

- local-minimal.yaml. This can execute bash transformations (no environment, no Docker image) locally.

- local.yaml. In addition, this can execute bash transformations that have a Docker image.

- local-with-generic.yaml. In addition, all other transformations (Python, compiled, conda environment) are executed inside the rpbs/seamless-minimal Docker image. It requires that `seamless-conda-env-export /tmp/SEAMLESS-MINIMAL` has been run first. Temporary conda environments are cached in `/tmp/JOBLESS-CONDA-ENV` (this dir must exist).

- local-with-generic-singularity.yaml. For the rpbs/seamless-minimal image, Singularity (must be installed) is used instead of Docker. It requires SEAMLESS_TOOLS_DIR to be defined (pointing to this Git repo). In addition, it requires SEAMLESS_MINIMAL_SINGULARITY_IMAGE to be defined and pointing to the seamless-minimal .sif file: see `seamless-cli-singularity/README.md` for instructions on how to generate it.

### Test suite

These are available in `jobless/tests`. They use the Transformer.docker_image values "ubuntu", "rpbs/seamless" and "rpbs/autodock". Make sure that these are available as Docker images in the place where the jobs will be run. NOTE: If you are using Jobless with Slurm+Singularity (not available among the test configs), have them as Singularity .sif files instead of as Docker images.

Launch a shell in a Seamless container with `seamless-bash`, or use the `seamless-framework` conda environment.

Make sure that the environment variable SEAMLESS_COMMUNION_PORT is set to the corresponding value in the Jobless .yaml file. SEAMLESS_COMMUNION_IP must point to the Jobless server IP address / hostname as well.

Run the tests `bash.py`, `docker_.py` and `autodock.py` with python3.
This will connect to a running Jobless instance. 
See the .expected-output files in the same folder.
If the output contains instead `Local computation has been disabled for this Seamless instance` or `Environment power cannot be granted: 'docker'`, then the test has failed, because a connection to Jobless
could not be made. `CacheMissError` indicates a failure in connecting to the Seamless database.

The above tests are for bash/bashdocker transformations and will work for all of the config files in `/jobless/config`. In addition, there are the following tests that require a config file with a generic jobhandler:

- `simple.py`: simple Python transformer.

- `parse-pdb.py`: a Python transformer with a conda environment.

- `compiled.py`: a C++ transformer.

### Cleaning the database after running the test suite

Use this if you can't run the test suite using a fresh database dir that you can delete afterwards.

After running the test suite in tests/, run "seamless-delete-database-from-log tests/jobless-test-dblog.txt" to clean up buffers, transformation results etc. from the database.

tests/jobless-test-dblog-ORIGINAL.txt is jobless-test-dblog.txt when all tests are run in the order: bash, docker_, simple, parse-pdb, compiled, autodock.
Use this if you have misplaced or scrambled your own jobless-test-dblog.txt 

### Testing Jobless in the general case

You can use Seamless's generic `seamless-serve-graph` command together with jobless, for any Seamless graph saved with `ctx.save_graph()` + `ctx.save_zip()` . For example, the "share-pdb" graph in `seamless-tests/highlevel` (bundled with the Seamless Docker image) requires only bash transformers:

```bash
graph_dir=/home/jovyan/seamless-tests/highlevel
seamless-upload-zip $graph_dir/share-pdb.zip
seamless-serve-graph $graph_dir/share-pdb.seamless --database --communion --ncores 0
```

Then, open [http://localhost:5813/ctx/index.html]. 
Use `seamless-serve-graph-interactive` to get an IPython shell instead.

# FAIR server

STUB
