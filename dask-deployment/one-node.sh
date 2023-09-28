# Sets up Dask+Seamless (including hashserver and database)
# This is meant to run on a single node of a HPC cluster or a single cloud VM
# It requires a Dask+Seamless development conda environment 
#   (built with ./build-devel-env.sh) to be activated.
#
# It also requires a port range to be available on the node 
#  towards the exterior, e.g 60001-61000
#
# Syntax: ./one-node.sh 60001 61000
#
# It is possible to give a third argument "host", indicating the IP address where
# the server will listen.
# Set this to '0.0.0.0' in case of ssh tunnels, tunneling via Docker network, etc.
#
# The script will print out a number of environment variables to copy.
# These are to be defined on your own machine, where Seamless will launch jobs.

set -u -e
RANDOM_PORT_START=$1
RANDOM_PORT_END=$2

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

currdir=`python -c 'import os,sys;print(os.path.dirname(os.path.realpath(sys.argv[1])))' $0`
source $currdir/setup-db-hashserver-devel.sh
sleep 3
cd $currdir

#ip=$(getent hosts $HOSTNAME | awk '{print $1}')
ip=$(hostname -I | awk '{print $1}')
host="${3:-$ip}"

export SEAMLESS_DATABASE_IP=localhost
export DASK_SCHEDULER_PORT=$(random_port)
export SEAMLESS_READ_BUFFER_SERVERS=http://localhost:$SEAMLESS_HASHSERVER_PORT
export SEAMLESS_WRITE_BUFFER_SERVER=http://localhost:$SEAMLESS_HASHSERVER_PORT

echo ' # For direct connection:'
echo ' #########################################################################'
echo ' export SEAMLESS_DATABASE_IP='$ip
echo ' export SEAMLESS_DATABASE_PORT='$SEAMLESS_DATABASE_PORT
echo ' export SEAMLESS_READ_BUFFER_SERVERS='http://$ip:$SEAMLESS_HASHSERVER_PORT
echo ' export SEAMLESS_WRITE_BUFFER_SERVER='http://$ip:$SEAMLESS_HASHSERVER_PORT
echo ' export DASK_SCHEDULER_ADDRESS='tcp://$ip:$DASK_SCHEDULER_PORT
echo ' #########################################################################'
echo 
echo ' # For seamless-delegate-ssh:'
echo ' #########################################################################'
echo ' export SEAMLESS_SSH_HOST='$HOSTNAME
echo ' export SEAMLESS_SSH_DATABASE_PORT='$SEAMLESS_DATABASE_PORT
echo ' export SEAMLESS_SSH_HASHSERVER_PORT='$SEAMLESS_HASHSERVER_PORT
echo ' export SEAMLESS_SSH_DASK_SCHEDULER_PORT='$DASK_SCHEDULER_PORT
echo ' #########################################################################'
echo ''

python3 local.py --host $host --port $DASK_SCHEDULER_PORT
