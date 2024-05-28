import asyncio
import os
import socket
import subprocess
import json
import time
import traceback
from aiohttp import web
import anyio
import tempfile
import dask

from seamless import CacheMissError
from seamless.highlevel import Checksum
from seamless.core.cache.buffer_remote import can_read_buffer
from dask.distributed import Client
from dask.distributed import WorkerPlugin

def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0

def get_conda_envs():
    try:
        from conda.cli import python_api as conda_python_api
    except ImportError:
        conda_python_api = None
    if conda_python_api is None:
        raise RuntimeError("Conda Python API not available")
    info, stderr, return_code = conda_python_api.run_command(conda_python_api.Commands.INFO, ["-e", "--json"])
    if return_code != 0:
        raise RuntimeError("Conda error:\n" + stderr)
    existing_envs = json.loads(info)["envs"]
    existing_envs = [os.path.split(eenv)[1] for eenv in existing_envs]
    return existing_envs

def run_command(command):
    command_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
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
    command_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
    command_tf2 = tempfile.NamedTemporaryFile(mode='w', delete=False)
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

def execute(checksum, dunder, *, fingertip, scratch):
    from dask.distributed import get_worker
    import os
    import logging
    logger = logging.getLogger("distributed.worker")

    import os
    if os.environ.get("DOCKER_IMAGE"): # we are running inside a Docker image
        SEAMLESS_SCRIPTS_DIR = "/home/jovyan/seamless-scripts"
    else:    
        SEAMLESS_SCRIPTS_DIR = os.environ["SEAMLESS_SCRIPTS_DIR"]
    global_info = get_worker().plugins["seamless"].global_info
    print("EXECUTE", checksum)
    logger.info("EXECUTE " + checksum)
    try:
        dundercmd=""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        global_info_file = tempfile.NamedTemporaryFile("w+t",delete=False)
        global_info_file.write(json.dumps(global_info))
        global_info_file.close()
        fingertipstr = "--fingertip" if fingertip else "" 
        scratchstr = "--scratch" if scratch else ""
        command = f"""
python {SEAMLESS_SCRIPTS_DIR}/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    {fingertipstr} {scratchstr}"""    
        print("RUN COMMAND", command)
        logger.info("RUN COMMAND " + command)

        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
        else: 
            result = None
            output = run_command(command)
        print("DONE", checksum)
        logger.info("DONE " + checksum)
        return result, output

    finally:
        os.unlink(global_info_file.name)
        if dunder is not None:
            os.unlink(tf.name)
        

def execute_in_existing_conda(checksum, dunder, conda_env_name, *, fingertip, scratch):
    from dask.distributed import get_worker
    import os
    import logging
    logger = logging.getLogger("distributed.worker")

    if os.environ.get("DOCKER_IMAGE"): # we are running inside a Docker image
        SEAMLESS_SCRIPTS_DIR = "/home/jovyan/seamless-scripts"
    else:    
        SEAMLESS_SCRIPTS_DIR = os.environ["SEAMLESS_SCRIPTS_DIR"]


    CONDA_ROOT = os.environ.get("CONDA_ROOT", None)
    global_info = get_worker().plugins["seamless"].global_info
    print(f"EXECUTE {checksum} in conda {conda_env_name}")
    logger.info(f"EXECUTE {checksum} in conda {conda_env_name}")

    try:
        dundercmd=""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundercmd = f"--dunder {dunderfile}"
        global_info_file = tempfile.NamedTemporaryFile("w+t",delete=False)
        global_info_file.write(json.dumps(global_info))
        global_info_file.close()
        fingertipstr = "--fingertip" if fingertip else "" 
        scratchstr = "--scratch" if scratch else ""
        command = f"""
source {CONDA_ROOT}/etc/profile.d/conda.sh
conda activate {conda_env_name}
python {SEAMLESS_SCRIPTS_DIR}/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    {fingertipstr} {scratchstr}"""    
        print("RUN COMMAND", command)
        logger.info("RUN COMMAND " + command)

        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
        else: 
            result = None
            output = run_command(command)
        print("DONE", checksum)
        logger.info("DONE " + checksum)
        return result, output
    finally:
        if dunder is not None:
            os.unlink(tf.name)

def execute_in_docker(checksum, dunder, env, docker_conf, *, fingertip, scratch, os_env):
    from dask.distributed import get_worker
    import os
    import logging

    logger = logging.getLogger("distributed.worker")

    global_info = get_worker().plugins["seamless"].global_info
    print("EXECUTE", checksum)
    logger.info("EXECUTE " + checksum)

    try:
        dundercmd=""
        dundermount = ""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"

        global_info_file = tempfile.NamedTemporaryFile("w+t",delete=False)
        global_info_file.write(json.dumps(global_info))
        global_info_file.close()

        docker_image = docker_conf["name"]
        fingertipstr = "--fingertip" if fingertip else ""
        scratchstr = "--scratch" if scratch else ""
        command = f"""
SEAMLESS_DOCKER_IMAGE={docker_image}
SEAMLESS_DOCKER_HOST_IP={os_env["SEAMLESS_DOCKER_HOST_IP"]}
set +u
source seamless-fill-environment-variables
set -u

docker run --rm \
-e SEAMLESS_DATABASE_IP \
-e SEAMLESS_DATABASE_PORT \
-e SEAMLESS_READ_BUFFER_SERVERS \
-e SEAMLESS_WRITE_BUFFER_SERVER \
-e DOCKER_IMAGE={docker_image} \
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

def execute_in_docker_devel(checksum, dunder, env, docker_conf, *, fingertip, scratch, os_env):
    from dask.distributed import get_worker
    import os
    import logging
    logger = logging.getLogger("distributed.worker")

    global_info = get_worker().plugins["seamless"].global_info
    print("EXECUTE", checksum)
    logger.info("EXECUTE " + checksum)

    try:
        dundermount = ""
        dundercmd=""
        if dunder is not None:
            tf = tempfile.NamedTemporaryFile("w+t",delete=False)
            tf.write(json.dumps(dunder))
            tf.close()
            dunderfile = tf.name
            dundermount = f"-v {dunderfile}:{dunderfile}"
            dundercmd = f"--dunder {dunderfile}"

        global_info_file = tempfile.NamedTemporaryFile("w+t",delete=False)
        global_info_file.write(json.dumps(global_info))
        global_info_file.close()

        docker_image = docker_conf["name"]
        fingertipstr = "--fingertip" if fingertip else "" 
        scratchstr = "--scratch" if scratch else ""
        command = f"""
SEAMLESS_DOCKER_IMAGE={docker_image}
SEAMLESS_DOCKER_HOST_IP={os_env["SEAMLESS_DOCKER_HOST_IP"]}
set +u
source seamless-fill-environment-variables
set -u

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

def _run_job(client, checksum, dunder, fingertip, scratch):
    from seamless.core.direct.run import fingertip as do_fingertip
    checksum = Checksum(checksum)

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
    env_checksum2 = env_checksum if env_checksum is not None else ""
    docker_conf = env.get("docker")
    if is_bash:
        docker_conf = None
    if docker_conf is not None:
        execute_in_docker_func = execute_in_docker
        docker_image = docker_conf["name"]
        if docker_image.find("seamless-devel") > -1:
            execute_in_docker_func = execute_in_docker_devel

        os_env = {}
        for var in os.environ:
            if var.startswith("SEAMLESS"):
                os_env[var] = os.environ[var]
        fut = client.submit(
            execute_in_docker_func, checksum.hex(), dunder, env, docker_conf,
            fingertip=fingertip, scratch=scratch, os_env=os_env,
            # Dask arguments
            
            key="{}-{}-{}-{}".format(checksum.hex(), int(fingertip), int(scratch), env_checksum2),
            ## this will cause identical jobs to be scheduled only once. 
            # Disable during development, or if you are playing around with worker deployment. (TODO: assistant command line option)

            pure=False  # will cause identical jobs to be re-run... but only if key is disabled?
        )
        result, output = fut.result()
        return result, output, transformation

    conda_env_name = env.get("conda_env_name")
    if conda_env_name is not None:
        existing_envs = client.submit(
            get_conda_envs,
            pure=False  # will cause identical jobs to be re-run... but only if key is disabled?
        ).result()
        if conda_env_name in existing_envs:
            fut = client.submit(
                execute_in_existing_conda, checksum.hex(), dunder, conda_env_name, 
                fingertip=fingertip, scratch=scratch,
                # Dask arguments
                
                key="{}-{}-{}-{}".format(checksum.hex(), int(fingertip), int(scratch), env_checksum2),
                ## this will cause identical jobs to be scheduled only once. 
                # Disable during development, or if you are playing around with worker deployment. (TODO: assistant command line option)

                pure=False  # will cause identical jobs to be re-run... but only if key is disabled?
            )
            result, output = fut.result()
            return result, output, transformation

    if env.get("conda") is not None:
        if conda_env_name is not None:
            raise RuntimeError("""Non-existing conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe.""")
        else:
            # The mini dask assistant can't support the creation of new conda environments
            # using transformer environment definitions (in conda YAML) as a recipe
            # Let's try to launch it in the scheduler's Seamless environment
            pass
    else:    
        if conda_env_name is not None or docker_conf is not None:
            raise RuntimeError("""Non-existing Docker image or conda environment specified.
Please create it, or provide a conda environment definition that will be used as recipe.""")

    fut = client.submit(
        execute, checksum.hex(), dunder, 
        fingertip=fingertip, scratch=scratch,
        # Dask arguments
        
        key="{}-{}-{}-{}".format(checksum.hex(), int(fingertip), int(scratch), env_checksum2),
        ## this will cause identical jobs to be scheduled only once. 
        # Disable during development, or if you are playing around with worker deployment. (TODO: assistant command line option)

        pure=False  # will cause identical jobs to be re-run... but only if key is disabled?
    )
    result, output = fut.result()
    return result, output, transformation

_jobs = {}

async def launch_job(client, tf_checksum, tf_dunder, *, fingertip, scratch):
    tf_checksum = Checksum(tf_checksum).hex()
    job = None
    if (tf_checksum, fingertip, scratch) in _jobs:
        job, curr_dunder = _jobs[tf_checksum, fingertip, scratch]
        if curr_dunder != tf_dunder:
            job.cancel()
            _jobs.pop((tf_checksum, fingertip, scratch))
            job = None
    if job is None:
        coro = anyio.to_thread.run_sync(run_job, client, Checksum(tf_checksum), tf_dunder, fingertip, scratch)
        job = asyncio.create_task(coro)
        _jobs[tf_checksum, fingertip, scratch] = job, tf_dunder
    
    remove_job = True
    try:
        return await asyncio.wait_for(asyncio.shield(job), timeout=10.0)
    except asyncio.TimeoutError:
        result = web.Response(status=202) # just send it again, later
        remove_job = False
        return result
    finally:
        if remove_job:
            _jobs.pop((tf_checksum, fingertip, scratch), None)


def run_job(client, checksum, dunder, fingertip, scratch):
    try:
        result, output, transformation = _run_job(client, checksum, dunder, fingertip, scratch)
    except subprocess.CalledProcessError as exc:
        output = exc.output
        return web.Response(
                status=400,
                body=b"ERROR: Unknown error\nOutput:\n" + output 
            )            
        
    if result is not None:
        assert scratch and fingertip
    else:
        for trial in range(5):
            result = seamless.util.verify_transformation_success(checksum, transformation)
            if result is not None:
                break
            time.sleep(0.2)

        if not result:
            return web.Response(
                status=400,
                body=b"ERROR: Unknown error\nOutput:\n" + output 
            )            

        result = Checksum(result).hex()
        if not scratch and not can_read_buffer(result):
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
    def __init__(self, client, host, port):
        self.client = client
        self.host = host
        self.port = port

    async def _start(self):
        if is_port_in_use(self.host, self.port):
            print("ERROR: %s port %d already in use" % (self.host, self.port))
            raise Exception

        from anyio import to_thread
        to_thread.current_default_thread_limiter().total_tokens = 1000

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
            
            tf_checksum = Checksum(data["checksum"])
            scratch = bool(data.get("scratch", False))
            fingertip = bool(data.get("fingertip", False))

            global JOBCOUNTER
            try:
                JOBCOUNTER += 1
            except NameError:
                JOBCOUNTER = 1
            jobcounter = JOBCOUNTER
            print("JOB", jobcounter, tf_checksum, scratch, fingertip)
            tf_dunder = data["dunder"]
            response = await launch_job(self.client, tf_checksum, tf_dunder=tf_dunder, scratch=scratch, fingertip=fingertip)
            return response
        
        except Exception as exc:
            traceback.print_exc() ###
            body="ERROR: " + str(exc)
            return web.Response(
                status=400,
                body=body
            )            
        

class SeamlessWorkerPlugin(WorkerPlugin):
    async def setup(self, worker):
        import json
        import logging
        import multiprocessing
        logger = logging.getLogger("distributed.worker")

        try:
            from seamless.core.transformation import get_global_info
        except ImportError:
            raise RuntimeError("Seamless must be installed on your Dask cluster") from None   

        def pr(msg):
            print(msg)
            logger.info(msg)
        
        pr("Worker SETUP")

        with multiprocessing.Pool(1) as p:
            fut = p.apply_async(get_global_info)
            for _ in range(100):  # allow 100 seconds for get_global_info
                if fut.ready():
                    break
                await asyncio.sleep(1)
            global_info = fut.get(timeout=1)
        
        self.global_info = global_info

        pr("Seamless global info:")
        pr(json.dumps(self.global_info))
        pr("Worker up")

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
        "scheduler_address",
        help="Dask scheduler address"
    )

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
    print("Connecting...")
    seamless.delegate(level=3)

    client = Client(args.scheduler_address)

    try:
        client.register_plugin(SeamlessWorkerPlugin(), name="seamless")
    except AttributeError:
        client.register_worker_plugin(SeamlessWorkerPlugin(), name="seamless")
    
    server = JobSlaveServer(client, args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
