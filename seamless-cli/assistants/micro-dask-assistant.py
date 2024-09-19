import asyncio
import json
import os
import socket
import time
import traceback
import anyio
from aiohttp import web
import dask
import logging

from seamless import Checksum, CacheMissError
from seamless.checksum.buffer_remote import can_read_buffer
from dask.distributed import Client
from dask.distributed import WorkerPlugin


logging.basicConfig(format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0


### Remote code


def setup(worker):

    print("Worker SETUP")
    if getattr(worker, "global_info", None):
        return
    try:
        import seamless.workflow

        seamless.workflow._original_event_loop = (
            asyncio.get_event_loop()
        )  # EVIL but needed for restarts
        from seamless.workflow.core.transformation import (
            get_global_info,
            execution_metadata0,
        )
        from seamless.workflow.core.cache.transformation_cache import (
            transformation_cache,
        )
        from seamless.workflow.util import set_unforked_process
        from seamless.workflow.metalevel.unbashify import get_bash_checksums
        from seamless.workflow.core.direct.run import set_dummy_manager
        from seamless.checksum.buffer_cache import buffer_cache
    except ImportError:
        raise RuntimeError("Seamless must be installed on your Dask cluster") from None

    # To hold on fingertipped buffers for longer
    buffer_cache.LIFETIME_TEMP = 600.0
    buffer_cache.LIFETIME_TEMP_SMALL = 1200.0

    seamless.config.set_ncores(worker.state.nthreads)
    set_unforked_process()
    seamless.delegate(level=3)
    get_bash_checksums()
    ###transformation_cache.stateless = True
    global_info = get_global_info(force=True)
    set_dummy_manager()
    execution_metadata0["Executor"] = "micro-dask-assistant-worker"
    print("Seamless global info:")
    print(json.dumps(global_info))
    worker.global_info = global_info
    print("Worker up")


class SeamlessWorkerPlugin(WorkerPlugin):
    def setup(self, worker):
        setup(worker)


def client_submit(client, *args, **kwargs):
    MAX_RESUBMIT = 3
    for _ in range(MAX_RESUBMIT - 1):
        try:
            return client.submit(*args, **kwargs)
        except Exception:
            if client.scheduler is None:
                client.start()
            client.restart()
    return client.submit(*args, **kwargs)


def run_transformation_dask(transformation_checksum, tf_dunder, fingertip, scratch):
    import json
    import time
    import seamless
    import seamless.workflow.core.direct.run

    if seamless.workflow.core.direct.run._dummy_manager is None:
        from dask.distributed import get_worker

        setup(get_worker())
    from seamless.workflow.core.direct.run import (
        get_dummy_manager,
        fingertip as do_fingertip,
    )
    from seamless import CacheMissError

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    manager = get_dummy_manager()

    transformation_checksum = Checksum(transformation_checksum)
    print("WORKER START TASK", transformation_checksum, fingertip, scratch)

    last_exc = None
    for trials in range(1):
        try:
            transformation_buffer = do_fingertip(transformation_checksum.bytes())
            if transformation_buffer is None:
                raise CacheMissError(transformation_checksum)

            transformation = json.loads(transformation_buffer.decode())

            lang = transformation.get("__language__")
            if not lang.startswith("<"):
                for k, v in transformation.items():
                    if not k.startswith("__"):
                        _, _, pin_checksum = v
                        try:
                            pin_checksum = Checksum(pin_checksum)
                        except Exception:
                            raise ValueError(
                                f'Invalid checksum for pin "{k}": "{pin_checksum}"'
                            ) from None
                        try:
                            pin_buffer = do_fingertip(pin_checksum.value)
                        except CacheMissError:
                            # Don't try too hard now, since we have nested event loops
                            pass
                        # if pin_buffer is None:
                        #    raise CacheMissError(pin_buffer)

            result_checksum = seamless.run_transformation(
                transformation_checksum.hex(),
                tf_dunder=tf_dunder,
                fingertip=fingertip,
                scratch=scratch,
                manager=manager,
            )
            if scratch and fingertip:
                if result_checksum is None:
                    raise CacheMissError
                result = do_fingertip(result_checksum)
                if result is None:
                    raise CacheMissError(result_checksum)
            else:
                for trial in range(5):
                    result = seamless.workflow.util.verify_transformation_success(
                        transformation_checksum, transformation
                    )
                    if result is not None:
                        break
                    time.sleep(0.2)

            if result is None:
                raise CacheMissError
            print("WORKER END TASK", transformation_checksum, fingertip, scratch)
            return result

        except CacheMissError as exc:
            import traceback

            traceback.print_exc()
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc from None


### /remote code

_jobs = {}


async def launch_job(jobslaveserver, checksum, tf_dunder, *, fingertip, scratch):
    global JOBCOUNTER
    checksum = Checksum(checksum).hex()
    job = None
    if (checksum, fingertip, scratch) in _jobs:
        job, curr_dunder = _jobs[checksum, fingertip, scratch]
        if curr_dunder != tf_dunder:
            job.cancel()
            _jobs.pop((checksum, fingertip, scratch))
            job = None
    if job is None:
        try:
            JOBCOUNTER += 1
        except NameError:
            JOBCOUNTER = 1

        logger.info(f"JOB {JOBCOUNTER} {checksum}")
        coro = anyio.to_thread.run_sync(
            run_job, jobslaveserver, Checksum(checksum), tf_dunder, fingertip, scratch
        )
        job = asyncio.create_task(coro)
        _jobs[checksum, fingertip, scratch] = job, tf_dunder

    remove_job = True
    try:
        return await asyncio.wait_for(asyncio.shield(job), timeout=10.0)
    except asyncio.TimeoutError:
        result = web.Response(status=202)  # just send it again, later
        remove_job = False
        return result
    finally:
        if remove_job:
            _jobs.pop((checksum, fingertip, scratch), None)


def run_job(jobslaveserver, checksum, tf_dunder, fingertip, scratch):
    import seamless
    from seamless.workflow.core.direct.run import fingertip as do_fingertip

    transformation_buffer = do_fingertip(checksum.bytes())
    if transformation_buffer is None:
        raise CacheMissError(checksum.hex())
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

    client = jobslaveserver.client
    if client.status not in ("running", "connecting", "newly-created"):
        client = create_client(jobslaveserver.scheduler_address)
        jobslaveserver.client = client
        time.sleep(5)
    with dask.annotate(resources=resources):
        result = client_submit(
            client,
            run_transformation_dask,
            checksum,
            tf_dunder=tf_dunder,
            fingertip=fingertip,
            scratch=scratch,
            # Dask arguments
            key=checksum.hex(),
            pure=False,  # set pure to False since we want to be able to re-submit failed jobs
        )
    result_value = result.result()
    if result_value is None:
        return web.Response(status=400, body=f"Unknown failure")

    if not (scratch and fingertip):
        for trial in range(5):
            result = seamless.workflow.util.verify_transformation_success(
                checksum, transformation
            )
            if result is not None:
                break
            time.sleep(0.2)

        if not result:
            return web.Response(
                status=400,
                body="ERROR: Unknown error (result not in database)\nResult checksum:\n"
                + Checksum(result_value).hex(),
            )

        result = Checksum(result).hex()
        if not scratch:
            for trial in range(50):
                if can_read_buffer(result):
                    break
                time.sleep(0.2)
            else:
                return web.Response(status=404, body=f"CacheMissError: {result}")
    else:
        result = result_value

    ### TODO: wait for a use case where this helps...
    ### # Wait two seconds to give slow networks a chance to update the database/buffer
    ### import time
    ### time.sleep(2)

    return web.Response(status=200, body=result)


class JobSlaveServer:
    future = None

    def __init__(self, client, host, port):
        self.client = client
        self.host = host
        self.port = port
        self.scheduler_address = client.scheduler.address

    async def _start(self):
        if is_port_in_use(self.host, self.port):
            logger.error("%s port %d already in use" % (self.host, self.port))
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

            checksum = Checksum(data["checksum"])
            scratch = bool(data.get("scratch", False))
            fingertip = bool(data.get("fingertip", False))

            """
            from seamless.workflow.core.direct.run import fingertip as do_fingertip
            import json
            print("RQ", json.loads(do_fingertip(checksum.hex()).decode()))
            ###print("DUNDER", data["dunder"])
            """
            tf_dunder = data["dunder"]
            response = await launch_job(
                self,
                checksum,
                tf_dunder=tf_dunder,
                scratch=scratch,
                fingertip=fingertip,
            )
            return response
        except Exception as exc:
            traceback.print_exc()  ###
            body = "ERROR: " + str(exc)
            return web.Response(status=400, body=body)


def create_client(scheduler_address):
    client = Client(scheduler_address)
    try:
        client.register_plugin(SeamlessWorkerPlugin())
    except AttributeError:
        client.register_worker_plugin(SeamlessWorkerPlugin())
    return client


if __name__ == "__main__":
    import argparse

    env = os.environ
    parser = argparse.ArgumentParser(
        description="""Micro dask assistant.
Transformations are directly forwarded to a remote Dask scheduler.                                    

The Dask scheduler must have started up in a Seamless-compatible way,
see seamless-tools/dask-deployment/example.py .
                                     
Dask clusters are homogeneous in environment.
No support for using transformer environment definitions (conda YAML) 
as a recipe. provided names of Docker images and conda environments are 
ignored.
                                     
Meta information is mostly ignored. No support for arbitrary Dask resources.
"""
    )

    default_port = int(env.get("SEAMLESS_ASSISTANT_PORT", -1))

    parser.add_argument("scheduler_address", help="Dask scheduler address")

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
        action="store_true",
    )

    args = parser.parse_args()
    if args.port == -1:
        raise ValueError(
            "Network port is not defined, neither as --port nor as SEAMLESS_ASSISTANT_PORT variable"
        )

    import seamless

    print("Connecting...")
    seamless.delegate(level=3)  # for can_read_result and input fingertipping

    server = JobSlaveServer(create_client(args.scheduler_address), args.host, args.port)
    server.start()

    loop = asyncio.get_event_loop()
    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
