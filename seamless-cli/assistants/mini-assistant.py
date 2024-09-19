import asyncio
import os
import socket
import subprocess
import json
import time
import traceback
from aiohttp import web
import anyio
from seamless import Checksum, CacheMissError
from seamless.checksum.buffer_remote import can_read_buffer
import logging

try:
    import docker
except ImportError:
    docker = None
try:
    from conda.cli import python_api as conda_python_api
except ImportError:
    conda_python_api = None
import tempfile

import os

logging.basicConfig(format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if os.environ.get("DOCKER_IMAGE"):  # we are running inside a Docker image
    SEAMLESS_SCRIPTS_DIR = "/home/jovyan/seamless-scripts"
else:
    SEAMLESS_SCRIPTS_DIR = os.environ["SEAMLESS_SCRIPTS_DIR"]
CONDA_ROOT = os.environ.get("CONDA_ROOT", None)


def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0


def run_command(command):
    command_tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
    try:
        command_tf.write("set -u -e\n")
        command_tf.write(command)
        command_tf.close()
        os.chmod(command_tf.name, 0o777)
        return subprocess.check_output(
            command_tf.name,
            shell=True,
            executable="/bin/bash",
            stderr=subprocess.STDOUT,
        )
    finally:
        os.unlink(command_tf.name)


def run_command_with_outputfile(command):
    command_tf = tempfile.NamedTemporaryFile(mode="w", delete=False)
    command_tf2 = tempfile.NamedTemporaryFile(mode="w", delete=False)
    outfile = command_tf2.name
    try:
        command_tf.write("set -u -e\n")
        command_tf.write(command + " --output " + outfile)
        command_tf.close()
        command_tf2.close()
        os.chmod(command_tf.name, 0o777)
        output = subprocess.check_output(
            command_tf.name,
            shell=True,
            executable="/bin/bash",
            stderr=subprocess.STDOUT,
        )
        if not os.path.exists(outfile):
            raise Exception("Empty outputfile")
        with open(outfile, "rb") as f:
            return f.read(), output
    finally:
        os.unlink(command_tf.name)
        os.unlink(command_tf2.name)


def execute_in_existing_conda(checksum, dunder, conda_env_name, *, fingertip, scratch):
    try:
        dundercmd = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t", delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        fingertipstr = "--fingertip" if fingertip else ""
        scratchstr = "--scratch" if scratch else ""
        command = f"""
source {CONDA_ROOT}/etc/profile.d/conda.sh
conda activate {conda_env_name}
python {SEAMLESS_SCRIPTS_DIR}/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    {fingertipstr} {scratchstr}"""
        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
            return result, output
        else:
            output = run_command(command)
            return None, output
    finally:
        if dunder is not None:
            os.unlink(tf.name)


def execute(checksum, dunder, *, fingertip, scratch):
    try:
        dundercmd = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t", delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        fingertipstr = "--fingertip" if fingertip else ""
        scratchstr = "--scratch" if scratch else ""
        command = f"""
python {SEAMLESS_SCRIPTS_DIR}/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    {fingertipstr} {scratchstr}"""
        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
            return result, output
        else:
            output = run_command(command)
            return None, output

    finally:
        if dunder is not None:
            os.unlink(tf.name)


def execute_in_docker(checksum, dunder, env, docker_conf, *, fingertip, scratch):
    docker_image = docker_conf["name"]
    if docker_image.find("seamless-devel") > -1:
        return execute_in_docker_devel(
            checksum, dunder, env, docker_conf, scratch=scratch
        )
    try:
        dundercmd = ""
        dundermount = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t", delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"
        docker_image = docker_conf["name"]
        fingertipstr = "--fingertip" if fingertip else ""
        scratchstr = "--scratch" if scratch else ""
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
    {fingertipstr} {scratchstr}"""
        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
            return result, output
        else:
            output = run_command(command)
            return None, output
    finally:
        if dunder is not None:
            os.unlink(tf.name)


def execute_in_docker_devel(checksum, dunder, env, docker_conf, *, fingertip, scratch):
    try:
        dundermount = ""
        dundercmd = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t", delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"
        docker_image = docker_conf["name"]
        fingertipstr = "--fingertip" if fingertip else ""
        scratchstr = "--scratch" if scratch else ""
        command = f"""
docker run --rm \
-e SEAMLESS_DATABASE_IP \
-e SEAMLESS_DATABASE_PORT \
-e SEAMLESS_READ_BUFFER_SERVERS \
-e SEAMLESS_WRITE_BUFFER_SERVER \
-v $SEAMLESS_SCRIPTS_DIR:/scripts \
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
    {fingertipstr} {scratchstr}"""
        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
            return result, output
        else:
            output = run_command(command)
            return None, output
    finally:
        if dunder is not None:
            os.unlink(tf.name)


def _run_job(checksum, dunder, fingertip, scratch):
    from seamless.workflow.core.direct.run import fingertip as do_fingertip

    transformation_buffer = do_fingertip(checksum.bytes())
    if transformation_buffer is None:
        raise CacheMissError(checksum.hex())
    transformation = json.loads(transformation_buffer.decode())
    is_bash = False
    if transformation["__language__"] == "bash":
        is_bash = True
    elif "bashcode" in transformation and "pins_" in transformation:
        is_bash = True
    env = {}
    env_checksum = None
    if dunder is not None:
        env_checksum = dunder.get("__env__")
    if env_checksum is not None:
        env_buffer = do_fingertip(env_checksum)
        env = json.loads(env_buffer.decode())
    docker_conf = env.get("docker")
    if is_bash:
        docker_conf = None
    if docker_conf is not None:
        if docker is None:
            raise RuntimeError("Docker is not available")
        docker_image = docker_conf["name"]
        client = docker.from_env()
        ok = True
        try:
            client.images.get(docker_image)
        except docker.errors.ImageNotFound:
            ok = False
        if ok:
            result, output = execute_in_docker(
                checksum, dunder, env, docker_conf, fingertip=fingertip, scratch=scratch
            )
            return result, output, transformation

    conda_env_name = env.get("conda_env_name")
    if conda_env_name is not None:
        if conda_python_api is None:
            raise RuntimeError("Conda Python API not available")
        info, stderr, return_code = conda_python_api.run_command(
            conda_python_api.Commands.INFO, ["-e", "--json"]
        )
        if return_code != 0:
            raise RuntimeError("Conda error:\n" + stderr)
        existing_envs = json.loads(info)["envs"]
        existing_envs = [os.path.split(eenv)[1] for eenv in existing_envs]
        if conda_env_name in existing_envs:
            result, output = execute_in_existing_conda(
                checksum, dunder, conda_env_name, fingertip=fingertip, scratch=scratch
            )
            return result, output, transformation

    if env.get("conda") is not None:
        if conda_env_name is not None:
            raise RuntimeError(
                """Non-existing conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe."""
            )
        else:
            # The mini assistant does not support the creation of new conda environments
            # using transformer environment definitions (in conda YAML) as a recipe
            # Let's try to launch it in the default Seamless environment
            pass
    else:
        if conda_env_name is not None or docker_conf is not None:
            raise RuntimeError(
                """Non-existing Docker image or conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe."""
            )

    result, output = execute(checksum, dunder, fingertip=fingertip, scratch=scratch)
    return result, output, transformation


_jobs = {}


async def launch_job(data):
    global JOBCOUNTER
    checksum = Checksum(data["checksum"]).hex()
    job = None
    if checksum in _jobs:
        job, curr_data = _jobs[checksum]
        if curr_data != data:
            job.cancel()
            _jobs.pop(checksum)
            job = None
    if job is None:
        try:
            JOBCOUNTER += 1
        except NameError:
            JOBCOUNTER = 1

        logger.info(f"JOB {JOBCOUNTER} {checksum}")

        coro = anyio.to_thread.run_sync(run_job, data)
        job = asyncio.create_task(coro)
        _jobs[checksum] = job, data

    remove_job = True
    try:
        return await asyncio.wait_for(asyncio.shield(job), timeout=10.0)
    except asyncio.TimeoutError:
        result = web.Response(status=202)  # just send it again, later
        remove_job = False
        return result
    finally:
        if remove_job:
            _jobs.pop(checksum, None)


def run_job(data):
    checksum = Checksum(data["checksum"])
    dunder = data.get("dunder", {})
    scratch = bool(data.get("scratch", False))
    fingertip = bool(data.get("fingertip", False))
    try:
        result, output, transformation = _run_job(checksum, dunder, fingertip, scratch)
    except subprocess.CalledProcessError as exc:
        output = exc.output
        return web.Response(
            status=400, body=b"ERROR: Unknown error\nOutput:\n" + output
        )

    if result is not None:
        assert data.get("scratch") and data.get("fingertip")
    else:
        for trial in range(5):
            result = seamless.workflow.util.verify_transformation_success(
                checksum, transformation
            )
            if result is not None:
                break
            time.sleep(0.2)

        if not result:
            return web.Response(
                status=400, body=b"ERROR: Unknown error\nOutput:\n" + output
            )

        result = Checksum(result).hex()
        if not scratch and not can_read_buffer(result):
            return web.Response(status=404, body=f"CacheMissError: {result}")

    return web.Response(status=200, body=result)


class JobSlaveServer:
    future = None

    def __init__(self, host, port, sock):
        self.host = host
        self.port = port
        self.sock = sock

    async def _start(self):
        if self.sock is None:
            if is_port_in_use(self.host, self.port):
                print("ERROR: %s port %d already in use" % (self.host, self.port))
                raise Exception

        from anyio import to_thread

        to_thread.current_default_thread_limiter().total_tokens = 1000

        app = web.Application(client_max_size=10e9)
        app.add_routes(
            [
                web.get("/config", self._get_config),
                web.put("/", self._put_job),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        if self.sock:
            print(f"Serving on socket {self.sock}")
            site = web.UnixSite(runner, self.sock)
        else:
            print(f"Serving on host {self.host}, port {self.port}")
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
        logger = logging.getLogger(__name__)
        data = request.rel_url.query
        agent = data.get("agent", "Anonymous")
        if agent != "HEALTHCHECK":
            logger.info(f"Connection from agent '{agent}'")
        return web.Response(status=200)

    async def _put_job(self, request: web.Request):
        try:
            data = await request.json()
            try:
                response = await launch_job(data)
                return response
            except RuntimeError as exc:
                body = traceback.format_exception_only(exc)[-1]
                return web.Response(status=400, body=body)

        except Exception as exc:
            traceback.print_exc()
            return web.Response(status=404, body="ERROR: " + str(exc))


if __name__ == "__main__":
    import argparse

    env = os.environ
    parser = argparse.ArgumentParser(
        description="""Mini assistant.
Transformations are executed by repeatedly launching run-transformation.py in a subprocess.
                                     
No support for using transformer environment definitions (conda YAML) as a recipe.

However, provided names of Docker images and conda environments are respected.
Note that non-bash transformers must have Seamless in their environment.
"""
    )

    parser.add_argument("--ncores", type=int, default=None)

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
        "--socket",
        type=str,
        help="Instead of serving on a host and port, serve on a Unix socket",
    )

    parser.add_argument(
        "--interactive",
        help="Do not enter a mainloop. Assumes that the script was opened with an interactive shell (e.g. ipython -i)",
        action="store_true",
    )
    parser.add_argument("--direct-print", dest="direct_print", action="store_true")
    parser.add_argument(
        "--verbose",
        help="Serve graph in verbose mode, setting the Seamless logger to INFO",
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        help="Serve graph in debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
        action="store_true",
    )

    args = parser.parse_args()
    if not args.socket:
        if args.port == -1:
            raise ValueError(
                "Network port is not defined, neither as --port nor as SEAMLESS_ASSISTANT_PORT variable"
            )

    import seamless

    seamless.delegate(level=3)

    from seamless.workflow.core.transformation import get_global_info

    global_info = get_global_info(force=True)
    global_info_file = tempfile.NamedTemporaryFile("w+t")
    json.dump(global_info, global_info_file)
    global_info_file.flush()

    host, port = args.host, args.port
    if args.socket:
        host = None
        port = None

    sock = os.path.realpath(args.socket) if args.socket else None
    try:
        server = JobSlaveServer(host, port, sock)
        server.start()

        loop = asyncio.get_event_loop()
        if not args.interactive:
            loop.run_until_complete(server.future)
            print("Press Ctrl+C to end")
            loop.run_forever()
    finally:
        if sock:
            os.unlink(sock)
