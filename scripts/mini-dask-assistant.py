import asyncio
import os
import socket
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
        try:
            import seamless
            from seamless.core.transformation import get_global_info, execution_metadata0
            from seamless.core.cache.transformation_cache import transformation_cache
            from seamless.util import set_unforked_process
            from seamless.metalevel.unbashify import get_bash_checksums 
        except ImportError:
            raise RuntimeError("Seamless must be installed on your Dask cluster") from None   
    
        seamless.config.set_ncores(worker.state.nthreads)
        set_unforked_process()
        seamless.delegate(level=3)
        get_bash_checksums()
        transformation_cache.stateless = True
        get_global_info()
        execution_metadata0["Executor"] = "mini-dask-assistant-worker"

def run_transformation(checksum, tf_dunder):
    from seamless import CacheMissError
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    checksum = Checksum(checksum)
    for trials in range(10):
        try:
            return seamless.run_transformation(checksum.hex(), fingertip=True, tf_dunder=tf_dunder)
        except CacheMissError:
            continue
    
### /remote code

_jobs = {}

async def launch_job(client, checksum, tf_dunder):
    checksum = Checksum(checksum).hex()
    job = None
    if checksum in _jobs:
        job, curr_dunder = _jobs[checksum]
        if curr_dunder != tf_dunder:
            job.cancel()
            _jobs.pop(checksum)
            job = None
    if job is None:
        coro = anyio.to_thread.run_sync(run_job, client, Checksum(checksum), tf_dunder)
        job = asyncio.create_task(coro)
        _jobs[checksum] = job, tf_dunder
    
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

def run_job(client, checksum, tf_dunder):
    known_resources = ("ncores",)
    resources = {}
    if tf_dunder is not None:
        meta = tf_dunder.get("__meta__", {})
    else:
        meta = {}
    for res in known_resources:
        if res in meta:
            resources[res] = meta[res]
    with dask.annotate(resources=resources):
        result = client.submit(
            run_transformation, checksum, tf_dunder=tf_dunder, key=checksum.hex()
        )
    checksum = result.result()
    if checksum is None:
        return web.Response(
            status=400,
            body=f"Unknown failure"
        )

    result = Checksum(checksum).hex()
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
        global JOBCOUNTER   
        try:
            data = await request.json()

            checksum = Checksum(data["checksum"])

            '''
            global JOBCOUNTER
            JOBCOUNTER += 1
            print("JOB", JOBCOUNTER, checksum)
            from seamless.core.direct.run import fingertip
            import json
            print("RQ", json.loads(fingertip(checksum.hex()).decode()))
            print("DUNDER", data["dunder"])
            '''

            tf_dunder = data["dunder"]
            response = await launch_job(self.client, checksum, tf_dunder)
            return response
        
        except Exception as exc:
            traceback.print_exc()
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
    seamless.config.delegate(level=3)

    client = Client(args.scheduler_address)
    try:
        client.register_plugin(SeamlessWorkerPlugin())
    except AttributeError:
        client.register_worker_plugin(SeamlessWorkerPlugin())

    server = JobSlaveServer(client, args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
