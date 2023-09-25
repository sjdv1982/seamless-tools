import asyncio
import os
import socket
import traceback
from aiohttp import web
import anyio
from seamless import CacheMissError
from seamless.highlevel import Checksum
from seamless.core.cache.buffer_remote import can_read_buffer
import dask
from dask.distributed import Client
from dask.distributed import WorkerPlugin

import os
SEAMLESS_TOOLS_DIR = os.environ["SEAMLESS_TOOLS_DIR"]

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
        except ImportError:
            raise RuntimeError("Seamless must be installed on your Dask cluster") from None   
    
        set_unforked_process()
        seamless.delegate(level=3)
        transformation_cache.stateless = True
        get_global_info()
        execution_metadata0["Executor"] = "mini-dask-assistant-worker"

def run_transformation(checksum, tf_dunder):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    checksum = Checksum(checksum)
    return seamless.run_transformation(checksum.hex(), fingertip=True, tf_dunder=tf_dunder)

### /remote code

def run_job(client, checksum, tf_dunder):
    result = client.submit(run_transformation, checksum, tf_dunder=tf_dunder, key=checksum.hex())
    checksum = result.result()

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

            checksum = Checksum(data["checksum"])

            '''
            from seamless.core.direct.run import fingertip
            import json
            print("RQ", json.loads(fingertip(checksum.hex()).decode()))
            print("DUNDER", data["dunder"])
            '''

            tf_dunder = data["dunder"]
            return run_job(self.client, checksum, tf_dunder)
        
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
Transformations are executed by repeatedly launching run-transformation.py in a subprocess.
Transformations are directly forwarded to a remote Dask scheduler.                                    

The Dask scheduler must have started up in a Seamless-compatible way,
see seamless-tools/dask-create-example-cluster.py .
                                     
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
    client.register_plugin(SeamlessWorkerPlugin())

    server = JobSlaveServer(client, args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()