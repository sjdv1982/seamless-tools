# Sets up a database and hashserver inside a Dask+Seamless conda environment
# A development environment is assumed, such as created by
#  build-environment-devel.sh
# This script is to be sourced inside a script that sets up the correct
# environment variables (see below), see one-node.sh for an example.

set -u -e

# Check that the correct environment variables have been defined:
x=$SEAMLESS_DATABASE_PORT
x=$SEAMLESS_HASHSERVER_PORT

# Check that the correct packages are there:
python -c 'import peewee, fastapi, uvicorn, dask, dask.distributed'

cd $SEAMLESS_TOOLS_DIR/tools
mkdir -p ~/.seamless/database
mkdir -p ~/.seamless/buffers
python3 database.py ~/.seamless/database/seamless.db --port $SEAMLESS_DATABASE_PORT --host 0.0.0.0 &
pid_db=$!
trap "echo exiting $pid_db; kill $pid_db" EXIT
sleep 1
HASHSERVERDIR=$SEAMLESS_TOOLS_DIR/seamless-cli/hashserver
cd $HASHSERVERDIR
python3 hashserver.py ~/.seamless/buffers --writable --port $SEAMLESS_HASHSERVER_PORT --host 0.0.0.0 &
pid_hs=$!
trap "echo exiting $pid_db $pid_hs; kill $pid_db $pid_hs" EXIT
sleep 1