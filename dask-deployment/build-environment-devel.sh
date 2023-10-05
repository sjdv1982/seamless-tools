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
if [ -z "$CONDA_EXE" ] || [ -z "$CONDA_SHLVL" ]; then
  echo 'conda must be installed' > /dev/stderr
  exit 1
fi

CONDA_DIR=$(python3 -c '
import os, pathlib
conda_shlvl = int(os.environ["CONDA_SHLVL"])
if conda_shlvl == 0:
    CONDA_DIR = str(pathlib.Path(os.environ["CONDA_EXE"]).parent.parent)
elif conda_shlvl == 1:
    CONDA_DIR = os.environ["CONDA_PREFIX"]
else:
    CONDA_DIR = os.environ["CONDA_PREFIX_1"]
print(CONDA_DIR)
')

source $CONDA_DIR/etc/profile.d/conda.sh

for i in $(seq ${CONDA_SHLVL}); do
    conda deactivate
done
conda activate

set -e
if [ -z "$PYTHONPATH" ]; then
  export PYTHONPATH=""
fi
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
echo 'The following file must exist; if not, go to SEAMLESS_TOOLS_DIR and do "git submodule update --init"'
ls $SEAMLESS_TOOLS_DIR/seamless-cli/hashserver/.git
echo "SILKDIR: location of the "silk" Git repo (https://github.com/sjdv1982/silk.git)"
echo "SILKDIR=$SILKDIR"
echo
echo "Building \"$environment_name\" conda environment..."
mamba create -n $environment_name 'python=3.10'
conda activate $environment_name
echo 'python=3.10' > $CONDA_PREFIX/conda-meta/pinned
mamba env update --file $SEAMLESSDIR/seamless-minimal-dependencies.yaml
mamba install -c conda-forge dask peewee fastapi uvicorn dask-jobqueue
pip install docker
conda env config vars set \
  SEAMLESSDIR=$SEAMLESSDIR \
  SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR \
  SILKDIR=$SILKDIR \
  HASHSERVERDIR=$SEAMLESS_TOOLS_DIR/seamless-cli/hashserver \
  PATH=${SEAMLESS_TOOLS_DIR}/seamless-cli:$SEAMLESSDIR/bin:${PATH} \
  PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH}
mkdir -p $CONDA_DIR/etc/conda/activate.d
mkdir -p $CONDA_DIR/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_DIR/etc/conda/activate.d/
