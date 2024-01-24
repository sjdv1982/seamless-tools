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
echo "SEAMLESSDIR: location of the "seamless" Git repo (https://github.com/sjdv1982/seamless.git)"
echo "SEAMLESSDIR=$SEAMLESSDIR"
echo
echo "SEAMLESS_TOOLS_DIR: location of the "seamless-tools" Git repo (https://github.com/sjdv1982/seamless-tools.git)"
echo "SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR"
echo
echo "SILKDIR: location of the "silk" Git repo (https://github.com/sjdv1982/silk.git)"
echo "SILKDIR=$SILKDIR"
echo
echo "Building \"$environment_name\" conda environment..."
mamba env create -n $environment_name --file $SEAMLESSDIR/seamless-minimal-dependencies.yaml
mamba install -n $environment_name -c conda-forge gcc gxx gfortran cython scipy wurlitzer -y
mamba install -n $environment_name -c conda-forge commentjson -y
mamba install -n $environment_name -c conda-forge black mypy types-requests sphinx recommonmark -y
mamba env update -n $environment_name --file $SEAMLESS_TOOLS_DIR/seamless-delegated-development.yaml
for i in $(seq ${CONDA_SHLVL}); do
    conda deactivate
done
conda activate $environment_name
pip install docker sphinx_rtd_theme
conda env config vars set \
  SEAMLESSDIR=$SEAMLESSDIR \
  SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR \
  SILKDIR=$SILKDIR \
  PATH=$SEAMLESSDIR/bin:${SEAMLESS_TOOLS_DIR}/seamless-cli:${PATH} \
  PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH} \
  SEAMLESS_DOCKER_IMAGE=seamless-devel

mkdir -p $CONDA_DIR/etc/conda/activate.d
mkdir -p $CONDA_DIR/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_DIR/etc/conda/activate.d/
conda deactivate
echo 'Done'