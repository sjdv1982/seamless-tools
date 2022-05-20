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