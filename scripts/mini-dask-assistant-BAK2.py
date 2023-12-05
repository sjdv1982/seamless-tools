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

    SEAMLESS_TOOLS_DIR = os.environ["SEAMLESS_TOOLS_DIR"]
    SEAMLESS_SCRIPTS = SEAMLESS_TOOLS_DIR + "/scripts" 
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
python {SEAMLESS_SCRIPTS}/run-transformation.py \
    {checksum} {dundercmd} \
    --global_info {global_info_file.name} \
    {fingertipstr} {scratchstr}"""    
        print("RUN COMMAND", command)
        logger.info("RUN COMMAND " + command)

        if fingertip and scratch:
            result, output = run_command_with_outputfile(command)
            return result, output
        else: 
            output = run_command(command)
            return None, output

    finally:
        os.unlink(global_info_file.name)
        if dunder is not None:
            os.unlink(tf.name)
        

def _run_job(checksum, dunder, scratch, fingertip):
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
    docker_conf = env.get("docker")
    if is_bash:
        docker_conf = None
    if docker_conf is not None:
        raise NotImplementedError

    conda_env_name = env.get("conda_env_name")
    if conda_env_name is not None:
        raise NotImplementedError
    
    fut = client.submit(
        execute, checksum.hex(), dunder, 
        fingertip=fingertip, scratch=scratch,
        # Dask arguments
        
        ###key="{}-{}-{}".format(checksum.hex(), int(fingertip), int(scratch)),
        ## this will cause identical jobs to be scheduled only once. 
        # Disable during development, or if you are playing around with worker deployment. (TODO: assistant command line option)

        pure=False  # will cause identical jobs to be re-run... but only if key is disabled?
    )
    result, output = fut.result()
    return result, output, transformation

_jobs = {}

async def launch_job(data):
    checksum = Checksum(data["checksum"]).hex()
    dunder = data.get("dunder", {})
    scratch = bool(data.get("scratch", False))
    fingertip = bool(data.get("fingertip", False))
    job = None
    if (checksum, fingertip, scratch) in _jobs:
        job, curr_data = _jobs[checksum, fingertip, scratch]
        if curr_data != data:
            job.cancel()
            _jobs.pop(checksum)
            job = None
    if job is None:
        coro = anyio.to_thread.run_sync(run_job, checksum, dunder, scratch, fingertip)
        job = asyncio.create_task(coro)
        _jobs[checksum, fingertip, scratch] = job, data
    
    remove_job = True
    try:
        return await asyncio.wait_for(asyncio.shield(job), timeout=10.0)
    except asyncio.TimeoutError:
        result = web.Response(status=202) # just send it again, later
        remove_job = False
        return result
    finally:
        if remove_job:
            _jobs.pop(checksum, None)


def run_job(checksum, dunder, scratch, fingertip):
    try:
        result, output, transformation = _run_job(checksum, dunder, scratch, fingertip)
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
    def __init__(self, host, port):
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
            try:
                response = await launch_job(data)
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


class SeamlessWorkerPlugin(WorkerPlugin):
    async def setup(self, worker):
        import json
        import logging
        import subprocess
        import tempfile
        import asyncio
        logger = logging.getLogger("distributed.worker")

        def pr(msg):
            print(msg)
            logger.info(msg)
        
        pr("Worker SETUP")
        
        # A very convoluted way of executing Seamless get_global_info() in a subprocess
        # but since we are using spawn instead of fork, not much we can do
        pythoncode = """
import sys
import json
tmpfile = sys.argv[1]

# Run this code only in a forked process
# Don't import seamless in the main worker process, it can give big thread+fork trouble!!!
# (if it doesn't give trouble, and you don't have big input or output buffers, 
# you may as well use the micro-dask-assistant)

from seamless.core.transformation import get_global_info
global_info = get_global_info(force=True)
with open(tmpfile, "w") as f:
    f.write(json.dumps(global_info))    
        """

        '''
        try:
            python_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
            python_tf.write(pythoncode)
            python_tf.close()
            result_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
            result_tf.close()
            cmd = f"python {python_tf.name} {result_tf.name}" 
            ###
            ###cmd = "python /users/sdevries/seamless-tools//scripts/run-transformation.py     691cfbfd43b51cf98150b3054d1cf0853d62ae0ff1a4411bfbef8ff7a2164665"

            proc = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            proc_coro = proc.communicate()
            epoch = 0
            pr("RUN CMD")
            while 1:
                try:
                    output, _ = await asyncio.wait_for(asyncio.shield(proc_coro), timeout=3)
                    break
                except asyncio.TimeoutError:
                    epoch += 1
                    pr("RUNNING..." + str(epoch))
            try:
                with open(result_tf.name) as f:
                    global_info = json.load(f)
                    assert isinstance(global_info, dict)
                    self.global_info = global_info
            except Exception:
                raise Exception(b"Cannot obtain global info, process output:" + output) from None
        finally:
            os.unlink(python_tf.name)
            os.unlink(result_tf.name)
        '''

        self.global_info = {"dummy": "dummy"}     ###

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
    
    server = JobSlaveServer(args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
