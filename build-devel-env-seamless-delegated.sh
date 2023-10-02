#!/bin/bash
if [ -z "$CONDA_PREFIX" ]; then
  echo 'conda needs to be activated' > /dev/stderr
  exit 1
fi

source $CONDA_PREFIX/etc/profile.d/conda.sh

set -e
if [ -z "$PYTHONPATH" ]; then
  export PYTHONPATH=""
fi
set -u -e
echo "SEAMLESSDIR: location of the "seamless" Git repo (https://github.com/sjdv1982/seamless.git)"
echo "SEAMLESSDIR=$SEAMLESSDIR"
echo
echo "SEAMLESS_TOOLS_DIR: location of the "seamless-tools" Git repo (https://github.com/sjdv1982/seamless-tools.git)"
echo "SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR"
echo
echo "SILKDIR: location of the "silk" Git repo (https://github.com/sjdv1982/silk.git)"
echo "SILKDIR=$SILKDIR"
echo
echo 'Building "seamless-delegated-development" conda environment...'
mamba env remove -n seamless-delegated-development
mamba env create --file seamless-delegated-development.yaml
for i in $(seq ${CONDA_SHLVL}); do
    conda deactivate
done
conda activate seamless-delegated-development
conda env config vars set \
  SEAMLESSDIR=$SEAMLESSDIR \
  SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR \
  SILKDIR=$SILKDIR \
  PATH=${SEAMLESS_TOOLS_DIR}/seamless-cli:$SEAMLESSDIR/bin:${PATH} \
  PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH} \
  SEAMLESS_DOCKER_IMAGE=seamless-devel

mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_PREFIX/etc/conda/activate.d/
conda deactivate
echo 'Done'