import asyncio
import json
import os
import random
import socket
import time
import traceback
import anyio
from aiohttp import web
from seamless import CacheMissError
from seamless.highlevel import Checksum
from seamless.core.cache.buffer_remote import can_read_buffer
import dask
from dask.distributed import Client
from dask.distributed import WorkerPlugin

def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0

### Remote code


class SeamlessWorkerPlugin(WorkerPlugin):
    def setup(self, worker):
        import tempfile
        import json
        print("Worker SETUP")
        try:
            import seamless
            seamless._original_event_loop = asyncio.get_event_loop() # EVIL but needed for restarts
            from seamless.core.transformation import get_global_info, execution_metadata0
            from seamless.core.cache.transformation_cache import transformation_cache
            from seamless.util import set_unforked_process
            from seamless.metalevel.unbashify import get_bash_checksums 
            from seamless.core.direct.run import set_dummy_manager
            from seamless.core.cache.buffer_cache import buffer_cache
        except ImportError:
            raise RuntimeError("Seamless must be installed on your Dask cluster") from None   

        ###seamless.util import is_forked
        ##assert not is_forked() # no nanny
        
        set_unforked_process() # nanny
        seamless.delegate(level=3)

        global_info = get_global_info()
        global_info_file = tempfile.NamedTemporaryFile("w+t")
        json.dump(global_info, global_info_file)
        global_info_file.flush()
        self.global_info_file = global_info_file

        print("Worker up")

def run_transformation_dask(transformation_checksum, tf_dunder, fingertip, scratch):
    import json
    import time
    import os
    import tempfile
    import subprocess
    from dask.distributed import get_worker
    import logging
    import asyncio
    logger = logging.getLogger("distributed.worker")

    SEAMLESS_TOOLS_DIR = os.environ["SEAMLESS_TOOLS_DIR"]
    SEAMLESS_SCRIPTS = SEAMLESS_TOOLS_DIR + "/scripts" 

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    global_info_file = get_worker().plugins["seamless"].global_info_file

    def execute(checksum, dunder, *, fingertip, scratch):

        try:
            dundercmd=""
            if dunder is not None:
                tf = tempfile.NamedTemporaryFile("w+t",delete=False)
                tf.write(json.dumps(dunder))
                tf.close()
                dunderfile = tf.name
                dundercmd = f"--dunder {dunderfile}"
            fingertipstr = "--fingertip" if fingertip else "" 
            scratchstr = "--scratch" if scratch else ""
            command = f"""
python {SEAMLESS_SCRIPTS}/run-transformation.py \
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

    def run_command(command):
        command_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
        try:
            command_tf.write(command + "--verbose\n")
            command_tf.close()
            os.chmod(command_tf.name, 0o777)
            """
            ''' # Could hang on dask.distributed because of forking + threading?'''
            return subprocess.check_output(
                command_tf.name,
                shell=True,
                executable="/bin/bash", 
                stderr=subprocess.STDOUT,
            )
            """
            
            command_tf3 = tempfile.NamedTemporaryFile(mode='w', delete=False)
            cmd = f"/bin/bash {command_tf.name} > {command_tf3.name} 2>&1"
            logger.info("RUN COMMAND: " + cmd)
            os.system(cmd)
            with open(command_tf3.name, "rb") as f:
                return f.read()
            

        finally:
            ###os.unlink(command_tf.name)
            try:
                ###os.unlink(command_tf3.name)
                pass
            except NameError:
                pass

    def run_command_with_outputfile(command):
        command_tf = tempfile.NamedTemporaryFile(mode='w', delete=False)
        command_tf2 = tempfile.NamedTemporaryFile(mode='w', delete=False)
        outfile = command_tf2.name
        try:
            command_tf.write("set -u -e\n")
            command_tf.write(command + " --verbose --output " + outfile)
            command_tf.close()
            command_tf2.close()
            os.chmod(command_tf.name, 0o777)
            
            ''' # Can hang on dask.distributed because of forking + threading? '''
            output = subprocess.check_output(
                command_tf.name,
                shell=True,
                executable="/bin/bash", 
                stderr=subprocess.STDOUT,
            )
            '''
            command_tf3 = tempfile.NamedTemporaryFile(mode='w', delete=False)
            cmd = f"/bin/bash {command_tf.name} > {command_tf3.name} 2>&1"
            logger.info("RUN COMMAND WITH OUTPUT: " + cmd)
            os.system(cmd)
            with open(command_tf3.name, "rb") as f:
                output = f.read()
            '''

            if not os.path.exists(outfile):
                raise Exception("Empty outputfile")
            with open(outfile, "rb") as f:
                return f.read(), output
        finally:
            os.unlink(command_tf.name)
            os.unlink(command_tf2.name)
            try:
                os.unlink(command_tf3.name)
            except NameError:
                pass

    def _run_job(tf_checksum, dunder, scratch, fingertip):
        from seamless.core.direct.run import fingertip as do_fingertip

        transformation_buffer = do_fingertip(tf_checksum.bytes())
        if transformation_buffer is None:
            raise CacheMissError(tf_checksum.hex())
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
            raise NotImplementedError #TODO: try to port it from the mini assistant

        conda_env_name = env.get("conda_env_name")
        if conda_env_name is not None:
            raise NotImplementedError #TODO: try to port it from the mini assistant
        
        if env.get("conda") is not None:
            raise NotImplementedError #TODO: try to port it from the mini assistant

        result, output = execute(tf_checksum, dunder, fingertip=fingertip, scratch=scratch)
        return result, output, transformation

    transformation_checksum = Checksum(transformation_checksum)
    print("WORKER START TASK", transformation_checksum, fingertip, scratch)
    logger.info("WORKER START TASK " + str(transformation_checksum))

    try:
        result, output, transformation = _run_job(transformation_checksum, tf_dunder, scratch, fingertip)
    except subprocess.CalledProcessError as exc:
        output = exc.output
        raise RuntimeError(b"ERROR: Unknown error\nOutput:\n" + output)
    
    print("WORKER END TASK", transformation_checksum, fingertip, scratch)
    logger.info("WORKER END TASK " + str(transformation_checksum))
    return result, output

        
### /remote code

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

def run_job(client, tf_checksum, tf_dunder, fingertip, scratch):
    from seamless.core.direct.run import fingertip as do_fingertip

    transformation_buffer = do_fingertip(tf_checksum.bytes())
    if transformation_buffer is None:
        raise CacheMissError(tf_checksum.hex())
    transformation = json.loads(transformation_buffer.decode())
    
    known_resources = ("ncores",)
    resources = {"ncores": 1}
    if tf_dunder is not None:
        meta = tf_dunder.get("__meta__", {})
    else:
        meta = {}
    for res in known_resources:
        if res in meta:
            resources[res] = meta[res]
    
    with dask.annotate(resources=resources):
        result = client.submit(
            run_transformation_dask, tf_checksum, tf_dunder=tf_dunder,
            fingertip=fingertip, scratch=scratch, 
            # Dask arguments
            ###key=checksum.hex(), 
            pure=False # set pure to False since we want to be able to re-submit failed jobs
                        # TODO: now effect because of key??
        )
    result_value = result.result()
    if result_value is None:
        return web.Response(
            status=400,
            body=f"Unknown failure"
        )

    result, output = result_value
    if result is not None:
        assert scratch and fingertip
    else:
        for trial in range(5):
            result = seamless.util.verify_transformation_success(tf_checksum, transformation)
            if result is not None:
                break
            time.sleep(0.2)

        if not result:
            return web.Response(
                status=400,
                body=b"ERROR: Unknown error\nOutput:\n" + output 
            )            

        result = Checksum(result).hex()

        if not scratch:
            for trial in range(50):
                if can_read_buffer(result):
                    break
                time.sleep(0.2)
            else:
                return web.Response(
                    status=404,
                    body=f"CacheMissError: {result}"
                )
        
    ### TODO: wait for a use case where this helps...
    ### # Wait two seconds to give slow networks a chance to update the database/buffer
    ### import time
    ### time.sleep(2)

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
            '''
            from seamless.core.direct.run import fingertip as do_fingertip
            import json
            print("RQ", json.loads(do_fingertip(tf_checksum.hex()).decode()))
            ###print("DUNDER", data["dunder"])
            '''
            tf_dunder = data["dunder"]
            response = await launch_job(client, tf_checksum, tf_dunder=tf_dunder, scratch=scratch, fingertip=fingertip)
            return response
        
        except Exception as exc:
            traceback.print_exc() ###
            body="ERROR: " + str(exc)
            return web.Response(
                status=400,
                body=body
            )            
            

if __name__ == "__main__":
    import argparse
    env = os.environ
    parser = argparse.ArgumentParser(description="""Mini-dask assistant.
Transformations are directly forwarded to a remote Dask scheduler.                                    

The Dask scheduler must have started up in a Seamless-compatible way,
see seamless-tools/dask-deployment/example.py .
                                     
Dask clusters are homogeneous in environment.
No support for using transformer environment definitions (conda YAML) 
as a recipe. provided names of Docker images and conda environments are 
ignored.
                                     
Meta information is also ignored. No support for Dask resources.
""")
                                     
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
