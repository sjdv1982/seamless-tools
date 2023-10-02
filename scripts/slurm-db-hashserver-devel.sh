#!/bin/bash
# Sets up a database and hashserver using a Slurm job
# inside a Dask+Seamless conda environment
#
# Note: this is a DEVELOPMENT version, requiring SEAMLESS_TOOLS_DIR to be defined
#
# It requires conda environments for the hashserver and the database to have been setup.
# See hashserver/environment.yml and tools/database.Dockerfile for the required packages 
#
# It also requires a port range to be available on the node 
#  towards the exterior, e.g 60001-61000
#
# Syntax: ./slurm-db-hashserver.sh 60001 61000
#
# It is possible to give a third argument "host", indicating the IP address where
# the server will listen. By default, this is 0.0.0.0
#
# Once it has started, it will generate a file (by default, ~/.seamless/seamless-env.sh)
# containing the network configuration of the Seamless hashserver and database.
# This file can then be included by:
# - Assistant scripts, e.g. a Slurm-based Seamless+Dask deployment script
# - Seamless clients that don't need an assistant (level 3 delegation or lower)

#SBATCH --job-name=slurm-db-hashserver
#SBATCH -o slurm-db-hashserver.out
#SBATCH -e slurm-db-hashserver.err

# 3 cores: can probably do with less
#SBATCH -c 3

# 500 MB of memory, should be plenty (?)
#SBATCH --mem=500MB

# If possible, run indefinitely
#SBATCH --time=0

set -u -e

RANDOM_PORT_START=$1
RANDOM_PORT_END=$2
host="${3:-0.0.0.0}"

x=$SEAMLESS_TOOLS_DIR

set +u -e

if [ -z "$CONDA_PREFIX" ]; then
  echo 'conda needs to be activated' > /dev/stderr
  exit 1
fi

source $CONDA_PREFIX/etc/profile.d/conda.sh

if [ -z "$HASHSERVER_CONDA_ENVIRONMENT" ]; then
    HASHSERVER_CONDA_ENVIRONMENT='hashserver'
    echo "HASHSERVER_CONDA_ENVIRONMENT not defined. Using default: hashserver" > /dev/stderr
fi

if [ -z "$HASHSERVER_BUFFER_DIR" ]; then
    HASHSERVER_BUFFER_DIR=$HOME/.seamless/buffers
    echo "HASHSERVER_BUFFER_DIR not defined. Using default: " $HASHSERVER_BUFFER_DIR > /dev/stderr
fi
mkdir -p $HASHSERVER_BUFFER_DIR

if [ -z "$DATABASE_CONDA_ENVIRONMENT" ]; then
    DATABASE_CONDA_ENVIRONMENT='seamless-database'
    echo "DATABASE_CONDA_ENVIRONMENT not defined. Using default: seamless-database" > /dev/stderr
fi

if [ -z "$DATABASE_DIR" ]; then
    DATABASE_DIR=$HOME/.seamless/database
    echo "DATABASE_DIR not defined. Using default: " $DATABASE_DIR > /dev/stderr
fi
mkdir -p $DATABASE_DIR


if [ -z "$ENVIRONMENT_OUTPUT_FILE" ]; then
    ENVIRONMENT_OUTPUT_FILE=$HOME/slurm-db-hashserver-env.sh
    echo "ENVIRONMENT_OUTPUT_FILE not defined. Using default: " $ENVIRONMENT_OUTPUT_FILE > /dev/stderr
fi

set -u -e

function random_port {
    echo $(python -c '
import sys
start, end = [int(v) for v in sys.argv[1:]]
import random
print(random.randint(start, end))
' $RANDOM_PORT_START $RANDOM_PORT_END)
}

export SEAMLESS_DATABASE_PORT=$(random_port)
export SEAMLESS_HASHSERVER_PORT=$(random_port)

for i in $(seq ${CONDA_SHLVL}); do
    conda deactivate
done

set -u -e

conda activate $HASHSERVER_CONDA_ENVIRONMENT

# Check that the correct packages are there:
python -c 'import fastapi, uvicorn'

conda deactivate

conda activate $DATABASE_CONDA_ENVIRONMENT

# Check that the correct packages are there:
python -c 'import peewee, aiohttp'

conda deactivate

conda activate $HASHSERVER_CONDA_ENVIRONMENT
cd $SEAMLESS_TOOLS_DIR/seamless-cli/hashserver
python3 -u hashserver.py $HASHSERVER_BUFFER_DIR --writable --port $SEAMLESS_HASHSERVER_PORT --host $host \
  >& $HASHSERVER_BUFFER_DIR/slurm-hashserver.log &
conda deactivate


conda activate $DATABASE_CONDA_ENVIRONMENT
cd $SEAMLESS_TOOLS_DIR/tools
python3 -u database.py $DATABASE_DIR/seamless.db --port $SEAMLESS_DATABASE_PORT --host $host \
  >& $DATABASE_DIR/slurm-db.log &
conda deactivate


ip=$(hostname -I | awk '{print $1}')

cat /dev/null > $ENVIRONMENT_OUTPUT_FILE 
echo ' # For direct connection:' >> $ENVIRONMENT_OUTPUT_FILE 
echo ' #########################################################################' >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_DATABASE_IP='$ip >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_DATABASE_PORT='$SEAMLESS_DATABASE_PORT >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_READ_BUFFER_SERVERS='http://$ip:$SEAMLESS_HASHSERVER_PORT >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_WRITE_BUFFER_SERVER='http://$ip:$SEAMLESS_HASHSERVER_PORT >> $ENVIRONMENT_OUTPUT_FILE 
echo ' #########################################################################' >> $ENVIRONMENT_OUTPUT_FILE 
echo >> $ENVIRONMENT_OUTPUT_FILE 
echo ' # For seamless-delegate-ssh:' >> $ENVIRONMENT_OUTPUT_FILE 
echo ' #########################################################################' >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_SSH_HASHSERVER_HOST='$HOSTNAME >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_SSH_HASHSERVER_PORT='$SEAMLESS_HASHSERVER_PORT >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_SSH_DATABASE_HOST='$HOSTNAME >> $ENVIRONMENT_OUTPUT_FILE 
echo ' export SEAMLESS_SSH_DATABASE_PORT='$SEAMLESS_DATABASE_PORT >> $ENVIRONMENT_OUTPUT_FILE 
echo ' #########################################################################' >> $ENVIRONMENT_OUTPUT_FILE 
echo '' >> $ENVIRONMENT_OUTPUT_FILE 

trap "rm -f $ENVIRONMENT_OUTPUT_FILE" EXIT

echo 'Database and hashserver are running...' > /dev/stderr
wait