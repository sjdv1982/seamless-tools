import asyncio
import os
import socket
import subprocess
import json
import traceback
from aiohttp import web
import anyio
from seamless import CacheMissError
from seamless.highlevel import Checksum
from seamless.core.cache.buffer_remote import can_read_buffer
import docker
import conda.cli.python_api
import tempfile

import os
SEAMLESS_TOOLS_DIR = os.environ["SEAMLESS_TOOLS_DIR"]
CONDA_ROOT = os.environ.get("CONDA_ROOT", None)

def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0

def run_command(command):
    command_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
    try:
        command_tf.write("set -u -e\n")
        command_tf.write(command)
        command_tf.close()
        os.chmod(command_tf.name, 0o777)
        subprocess.check_output(
            command_tf.name,
            shell=True,
            executable="/bin/bash", 
            stderr=subprocess.STDOUT,
        )
    finally:
        os.unlink(command_tf.name)

def execute_in_existing_conda(checksum, dunder, conda_env_name):
    try:
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        command = f"""
source {CONDA_ROOT}/etc/profile.d/conda.sh
conda activate {conda_env_name}
python $SEAMLESS_TOOLS_DIR/scripts/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    --fingertip
"""    
        run_command(command)
    finally:
        if dunder is not None:
            os.unlink(tf.name)

def execute(checksum, dunder):
    try:
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        command = f"""
python $SEAMLESS_TOOLS_DIR/scripts/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    --fingertip
"""    
        run_command(command)
    finally:
        if dunder is not None:
            os.unlink(tf.name)

def execute_in_docker(checksum, dunder, env, docker_conf):
    docker_image = docker_conf["name"]
    if docker_image.find("seamless-devel") > -1:
        return execute_in_docker_devel(checksum, dunder, env, docker_conf)
    try:
        dundermount = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"
        docker_image = docker_conf["name"]
        command = f"""
docker run --rm \
-e SEAMLESS_DATABASE_IP \
-e SEAMLESS_DATABASE_PORT \
-e SEAMLESS_READ_BUFFER_SERVERS \
-e SEAMLESS_WRITE_BUFFER_SERVER \
-e DOCKER_IMAGE={docker_image} \
-e DOCKER_VERSION="$SEAMLESS_DOCKER_VERSION" \
-v {global_info_file.name}:{global_info_file.name} \
-u `id -u` \
--group-add users \
{dundermount} \
{docker_image} \
start.sh python /scripts/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    --fingertip
"""    
        run_command(command)
    finally:
        if dunder is not None:
            os.unlink(tf.name)

def execute_in_docker_devel(checksum, dunder, env, docker_conf):
    try:
        dundermount = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"
        docker_image = docker_conf["name"]
        command = f"""
docker run --rm \
-e SEAMLESS_DATABASE_IP \
-e SEAMLESS_DATABASE_PORT \
-e SEAMLESS_READ_BUFFER_SERVERS \
-e SEAMLESS_WRITE_BUFFER_SERVER \
-v $SEAMLESS_TOOLS_DIR/scripts:/scripts \
-v $SEAMLESSDIR:/seamless \
-v $SILKDIR:/silk \
-e DOCKER_IMAGE={docker_image} \
-e DOCKER_VERSION="$SEAMLESS_DOCKER_VERSION" \
-e PYTHONPATH=/silk:/seamless \
-v {global_info_file.name}:{global_info_file.name} \
-u `id -u` \
--group-add users \
{dundermount} \
{docker_image} \
start.sh python /scripts/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    --fingertip
"""    
        run_command(command)
    finally:
        if dunder is not None:
            os.unlink(tf.name)


def _run_job(checksum, data):
    from seamless.core.direct.run import fingertip

    transformation_buffer = fingertip(checksum.bytes())
    if transformation_buffer is None:
        raise CacheMissError(checksum.hex())
    transformation = json.loads(transformation_buffer.decode())
    is_bash = False
    if transformation["__language__"] == "bash":
        is_bash = True
    elif "bashcode" in transformation and "pins_" in transformation:
        is_bash = True
    dunder = data["dunder"]
    env = {}
    env_checksum = dunder.get("__env__")
    if env_checksum is not None:
        env_buffer = fingertip(env_checksum)
        env = json.loads(env_buffer.decode())
    docker_conf = env.get("docker")
    if is_bash:
        docker_conf = None
    if docker_conf is not None:
        docker_image = docker_conf["name"]
        client = docker.from_env()
        ok = True
        try:
            client.images.get(docker_image)
        except docker.errors.ImageNotFound:
            ok = False
        if ok:
            return execute_in_docker(checksum, dunder, env, docker_conf)

    conda_env_name = env.get("conda_env_name")
    if conda_env_name is not None:
        info, stderr, return_code = conda.cli.python_api.run_command(conda.cli.python_api.Commands.INFO, ["-e", "--json"])        
        if return_code != 0:
            raise RuntimeError("Conda error:\n" + stderr)
        existing_envs = json.loads(info)["envs"]
        existing_envs = [os.path.split(eenv)[1] for eenv in existing_envs]
        if conda_env_name in existing_envs:
            return execute_in_existing_conda(checksum, dunder, conda_env_name)
    
    if env.get("conda") is not None:
        if conda_env_name is not None:
            raise RuntimeError("""Non-existing conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe.""")
        else:
            # The mini assistant does not support the creation of new conda environments
            # using transformer environment definitions (in conda YAML) as a recipe
            # Let's try to launch it in the default Seamless environment
            pass
    else:    
        if conda_env_name is not None or docker_conf is not None:
            raise RuntimeError("""Non-existing Docker image or conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe.""")
    
    return execute(checksum, dunder)

def run_job(data):
    checksum = Checksum(data["checksum"])
    try:
        _run_job(checksum, data)
    except subprocess.CalledProcessError as exc:
        output = exc.output
        try:
            output = output.decode()
        except UnicodeDecodeError:
            pass
        raise RuntimeError(output) from None

    result = seamless.config.database.get_transformation_result(checksum.bytes())
    if result is None:
        return web.Response(
            status=400,
            body="ERROR: Unknown error"
        )            

    result = Checksum(result).hex()
    if not can_read_buffer(result):
        return web.Response(
            status=404,
            body=f"CacheMissError: {result}"
        )

    return web.Response(
        status=200,
        body=result
    )



class JobSlaveServer:
    future = None
    def __init__(self, host, port):
        self.host = host
        self.port = port

    async def _start(self):
        if is_port_in_use(self.host, self.port):
            print("ERROR: %s port %d already in use" % (self.host, self.port))
            raise Exception

        app = web.Application(client_max_size=10e9)
        app.add_routes([
            web.get('/config', self._get_config),
            web.put('/', self._put_job),
        ])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

    def start(self):
        if self.future is not None:
            return
        coro = self._start()
        self.future = asyncio.ensure_future(coro)

    async def _get_config(self, request):
        # Return an empty response.
        # This causes Seamless clients to load their delegation config
        #  from environment variables
        return web.Response(
            status=200
        )

    async def _put_job(self, request:web.Request):        
        try:
            data = await request.json()
            #print("DATA", data)
            try:
                response = await anyio.to_thread.run_sync(run_job, data)
                return response
            except RuntimeError as exc:
                body = traceback.format_exception_only(exc)[-1]
                return web.Response(
                    status=400,
                    body=body
                )            
            

        except Exception as exc:
            traceback.print_exc()
            return web.Response(
                status=404,
                body="ERROR: " + str(exc)
            )

if __name__ == "__main__":
    import argparse
    env = os.environ
    parser = argparse.ArgumentParser(description="""Mini assistant.
Transformations are executed by repeatedly launching run-transformation.py in a subprocess.
                                     
No support for using transformer environment definitions (conda YAML) as a recipe.

However, provided names of Docker images and conda environments are respected.
Note that non-bash transformers must have Seamless in their environment.
""")
                                     
    parser.add_argument("--ncores",type=int,default=None)

    default_port = int(env.get("SEAMLESS_ASSISTANT_PORT", -1))

    parser.add_argument(
        "--port",
        type=int,
        help="Network port",
        default=default_port,
    )

    parser.add_argument(
        "--host",
        type=str,
        help="Network host",
        default="127.0.0.1",
    )

    parser.add_argument(
        "--interactive",
        help="Do not enter a mainloop. Assumes that the script was opened with an interactive shell (e.g. ipython -i)",
        action="store_true"
    )
    parser.add_argument("--direct-print", dest="direct_print", action="store_true")
    parser.add_argument(
        "--verbose",
        help="Serve graph in verbose mode, setting the Seamless logger to INFO",
        action="store_true"
    )
    parser.add_argument(
        "--debug",
        help="Serve graph in debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
        action="store_true"
    )

    args = parser.parse_args()
    if args.port == -1:
        raise ValueError("Network port is not defined, neither as --port nor as SEAMLESS_ASSISTANT_PORT variable")

    import seamless
    seamless.config.delegate(level=3)
    
    from seamless.core.transformation import get_global_info
    
    global_info = get_global_info({})
    global_info_file = tempfile.NamedTemporaryFile("w+t")
    json.dump(global_info, global_info_file)
    global_info_file.flush()

    server = JobSlaveServer(args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
