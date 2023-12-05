import asyncio
import os
import socket
import time
import traceback
from aiohttp import web
import tempfile
import anyio
import json

import dask
from dask.distributed import Client
from dask.distributed import WorkerPlugin

import seamless
from seamless import CacheMissError
from seamless.highlevel import Checksum
from seamless.core.cache.buffer_remote import can_read_buffer

def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0


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

async def run_transformation_dask(transformation_checksum, tf_dunder, fingertip, scratch):
    import os
    import aiohttp
    from aiohttp.client_exceptions import ServerDisconnectedError
    import logging
    logger = logging.getLogger("distributed.worker")
    socket_path = os.environ["SEAMLESS_TRANSFORMATION_SOCKET"]


    for wait_a_second in range(30):
        if os.path.exists(socket_path):
            break
        print(f"Waiting for socket {socket_path} to exist... {wait_a_second}")
        logger.info(f"Waiting for socket {socket_path} to exist... {wait_a_second}")
        await asyncio.sleep(1)
    else:
        raise RuntimeError("Socket {socket_path} was not created by worker startup script")
    print(f"Socket {socket_path} found")
    logger.info(f"Socket {socket_path} found")

    timeout = 20

    print(f"WORKER RUN {transformation_checksum}")
    logger.info(f"WORKER RUN {transformation_checksum}")

    conn = aiohttp.UnixConnector(path=socket_path)
    # we can't really re-use the session because of threads...
    async with aiohttp.ClientSession(connector=conn) as session:
        data={
            "checksum":transformation_checksum.hex(), 
            "dunder":tf_dunder, 
            "scratch": scratch, 
            "fingertip": fingertip
        }
        for retry in range(5):
            try:
                while 1:
                    async with session.put(url='http://localhost/', json=data,timeout=timeout) as response:
                        content = await response.read()
                        if response.status == 202:
                            await asyncio.sleep(0.1)
                            continue
                        if not (scratch and fingertip):
                            try:
                                content = content.decode()
                            except UnicodeDecodeError:
                                pass                
                        if response.status != 200:
                            msg1 = (f"Error {response.status} from assistant:")
                            if isinstance(content, bytes):
                                msg1 = msg1.encode()
                            err = msg1 + content
                            try:
                                if isinstance(err, bytes):
                                    err = err.decode()
                            except UnicodeDecodeError:
                                pass                                            
                            raise RuntimeError(err)
                        break
                break
            except ServerDisconnectedError:
                continue

    print(f"WORKER DONE {transformation_checksum}")
    logger.info(f"WORKER DONE {transformation_checksum}")
    return content

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

    if scratch and fingertip:
        return result_value
    else:
        for trial in range(5):
            result = seamless.util.verify_transformation_success(tf_checksum, transformation)
            if result is not None:
                break
            time.sleep(0.2)

        if not result:
            return web.Response(
                status=400,
                body=b"ERROR: Unknown error\nOutput:\n" + result_value
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
    def setup(self, worker):
        import os
        print("Worker SETUP")
        try:
            import seamless
        except ImportError:
            raise RuntimeError("Seamless must be installed on your Dask cluster") from None   

        if "SEAMLESS_TRANSFORMATION_SOCKET" not in os.environ:
            raise RuntimeError("""The Dask mini assistant requires SEAMLESS_TRANSFORMATION_SOCKET.
You might be using a deployment script designed for the Dask micro assistant.""")

if __name__ == "__main__":
    import argparse
    env = os.environ
    parser = argparse.ArgumentParser(description="""Mini-dask assistant.
Transformations are forwarded to a remote Dask scheduler, 
    which will forward them further to a running mini-assistant in --socket mode.

The Dask scheduler must have started up in a Seamless-compatible way,
see seamless-tools/dask-deployment/example.py .
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
