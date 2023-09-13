#!/bin/bash -i
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
conda activate seamless-delegated-development
conda env config vars set PATH=${SEAMLESS_TOOLS_DIR}/seamless-cli:$SEAMLESSDIR/bin:${PATH}
conda env config vars set PYTHONPATH=${SILKDIR}:${SEAMLESSDIR}:${PYTHONPATH}
mkdir -p $CONDA_PREFIX/etc/conda/activate.d
mkdir -p $CONDA_PREFIX/etc/conda/deactivate.d
cp ${SEAMLESSDIR}/bin/activate-seamless-mode.sh $CONDA_PREFIX/etc/conda/activate.d/
conda deactivate
echo 'Done'