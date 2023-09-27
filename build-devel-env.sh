#!/bin/bash
source $CONDA_PREFIX/etc/profile.d/conda.sh

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
conda activate $environment_name
conda env config vars set \
  SEAMLESSDIR=$SEAMLESSDIR \
  SEAMLESS_TOOLS_DIR=$SEAMLESS_TOOLS_DIR \
  SILKDIR=$SILKDIR \
  PATH=${SEAMLESS_TOOLS_DIR}/seamless-cli:$SEAMLESSDIR/bin:${PATH} \
  PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH}
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_PREFIX/etc/conda/activate.d/
conda deactivate
echo 'Done'