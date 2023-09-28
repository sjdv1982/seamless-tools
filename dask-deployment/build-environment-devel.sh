# Builds a python 3.10 environment containing: 
# - Dask
# - Seamless minimal (for now, the development version)
# - The required packages for hashserver and the Seamless database
#   (the latter is only strictly necessary if they are being launched 
#    locally, using setup.sh; not if they have been already deployed elsewhere)

# Once this environment has been built, you can
# - conda activate it
# - install any additional packages you may need, e.g. for machine learning.
#   Note that the installed Seamless dependencies are minimal and don't include
#   packages such as scipy or matplotlib, which are present in the Seamless 
#   Docker image.
# - Launch a Dask scheduler. It will need a Seamless database and hashserver.
#   You can run e.g. one-node.sh where all three will be launched at the same time.
#   The launch script should print out a number of environment variables to copy.
#   These are to be defined where Seamless is imported to launch jobs.

#!/bin/bash
if [ -z "$CONDA_PREFIX" ]; then
  echo 'conda needs to be activated' > /dev/stderr
  exit 1
fi

source $CONDA_PREFIX/etc/profile.d/conda.sh

set -u -e
environment_name=$1
echo 'Check that mamba is installed'
mamba -V > /dev/null
echo "SEAMLESSDIR: location of the "seamless" Git repo (https://github.com/sjdv1982/seamless.git)"
echo "SEAMLESSDIR=$SEAMLESSDIR"
ls $SEAMLESSDIR/.git > /dev/null
echo
echo "SEAMLESS_TOOLS_DIR: location of the "seamless-tools" Git repo (https://github.com/sjdv1982/seamless-tools.git)"
echo "SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR"
ls $SEAMLESS_TOOLS_DIR/.git > /dev/null
echo
echo 'The following file must exist; if not, do "git pull --recurse-submodules https://github.com/sjdv1982/seamless-tools.git"'
ls $SEAMLESS_TOOLS_DIR/seamless-cli/hashserver/.git
echo "SILKDIR: location of the "silk" Git repo (https://github.com/sjdv1982/silk.git)"
echo "SILKDIR=$SILKDIR"
echo
echo "Building \"$environment_name\" conda environment..."
mamba create -n $environment_name 'python=3.10'
conda activate $environment_name
echo 'python=3.10' > $CONDA_PREFIX/conda-meta/pinned
mamba env update --file $SEAMLESSDIR/seamless-minimal-dependencies.yaml
mamba install -c conda-forge dask peewee fastapi uvicorn
pip install docker
conda env config vars set \
  SEAMLESSDIR=$SEAMLESSDIR \
  SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR \
  SILKDIR=$SILKDIR \
  HASHSERVERDIR=$SEAMLESS_TOOLS_DIR/seamless-cli/hashserver \
  PATH=${SEAMLESS_TOOLS_DIR}/seamless-cli:$SEAMLESSDIR/bin:${PATH} \
  PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH}
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_PREFIX/etc/conda/activate.d/
