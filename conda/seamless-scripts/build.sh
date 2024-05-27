#!/bin/bash
set -u -e -x

mkdir -p $PREFIX/etc/conda/activate.d
mkdir -p $PREFIX/etc/conda/deactivate.d
cp -r $RECIPE_DIR/../../scripts $PREFIX/share/seamless-scripts
echo 'export SEAMLESS_SCRIPTS_DIR=${CONDA_PREFIX}/share/seamless-scripts' > $PREFIX/etc/conda/activate.d/seamless-scripts.sh
echo 'unset SEAMLESS_SCRIPTS_DIR' > $PREFIX/etc/conda/deactivate.d/seamless-scripts.sh