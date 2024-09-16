import asyncio
import os
import signal
import socket
import sys
import traceback
from aiohttp import web
import json
import seamless
from seamless import Checksum, CacheMissError


def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0


_jobs = {}

_dummy_manager = None


async def run_transformation(checksum, tf_dunder, fingertip, scratch):
    assert _dummy_manager is not None
    transformation_buffer = await _dummy_manager.cachemanager.fingertip(checksum)
    if transformation_buffer is None:
        raise CacheMissError(Checksum(checksum))
    transformation = json.loads(transformation_buffer.decode())
    for k, v in transformation.items():
        if not k.startswith("__"):
            _, _, pin_checksum = v
            await _dummy_manager.cachemanager.fingertip(pin_checksum)
    result_checksum = await seamless.direct.run_transformation_async(
        checksum, tf_dunder=tf_dunder, fingertip=fingertip, scratch=scratch
    )
    if scratch and fingertip:
        return await _dummy_manager.cachemanager.fingertip(result_checksum)
    else:
        return result_checksum


async def launch_job(checksum, tf_dunder, *, fingertip, scratch):
    checksum = Checksum(checksum).hex()
    job = None
    if checksum in _jobs:
        job, curr_dunder = _jobs[checksum]
        if curr_dunder != tf_dunder:
            job.cancel()
            _jobs.pop(checksum)
            job = None
    if job is None:
        coro = run_transformation(
            Checksum(checksum),
            fingertip=fingertip,
            tf_dunder=tf_dunder,
            scratch=scratch,
        )
        job = asyncio.create_task(coro)
        _jobs[checksum] = job, tf_dunder

    remove_job = True
    try:
        result = await asyncio.wait_for(asyncio.shield(job), timeout=10.0)
        if result is None:
            return web.Response(status=400, body="ERROR: Unknown error")

        if not (scratch and fingertip):
            result = Checksum(result).hex()

        return web.Response(status=200, body=result)
    except asyncio.TimeoutError:
        result = web.Response(status=202)  # just send it again, later
        remove_job = False
        return result
    finally:
        if remove_job:
            _jobs.pop(checksum, None)


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
        return web.Response(status=200)

    async def _put_job(self, request: web.Request):
        try:
            data = await request.json()

            checksum = Checksum(data["checksum"])
            scratch = bool(data.get("scratch", False))
            fingertip = bool(data.get("fingertip", False))

            """
            from seamless.workflow.core.direct.run import fingertip
            import json
            print("RQ", json.loads(fingertip(checksum.hex()).decode()))
            print("DUNDER", data["dunder"])
            """

            dunder = data["dunder"]
            response = await launch_job(
                checksum, tf_dunder=dunder, scratch=scratch, fingertip=fingertip
            )
            return response

        except Exception as exc:
            traceback.print_exc()
            return web.Response(status=400, body="ERROR: " + str(exc))


if __name__ == "__main__":
    import argparse

    env = os.environ
    parser = argparse.ArgumentParser(
        description="""Simple assistant.
"""
    )
    parser.add_argument("--time", type=float, default=None)
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
        "--interactive",
        help="Do not enter a mainloop. Assumes that the script was opened with an interactive shell (e.g. ipython -i)",
        action="store_true",
    )
    parser.add_argument("--direct-print", dest="direct_print", action="store_true")
    parser.add_argument(
        "--verbose",
        help="Verbose mode, setting the Seamless logger to INFO",
        action="store_true",
    )
    parser.add_argument(
        "--debug",
        help="Debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
        action="store_true",
    )

    args = parser.parse_args()
    if args.port == -1:
        raise ValueError(
            "Network port is not defined, neither as --port nor as SEAMLESS_ASSISTANT_PORT variable"
        )

    if args.debug:
        asyncio.get_event_loop().set_debug(True)
        import logging

        logging.basicConfig()
        logging.getLogger("seamless").setLevel(logging.DEBUG)
    elif args.verbose:
        import logging

        logging.basicConfig()
        logging.getLogger("seamless").setLevel(logging.INFO)

    import seamless

    from seamless.workflow.core.transformation import (
        get_global_info,
        execution_metadata0,
    )
    from seamless.workflow.core.cache.transformation_cache import transformation_cache

    transformation_cache.stateless = True

    get_global_info(force=True)
    execution_metadata0["Executor"] = "micro-assistant"

    seamless.delegate(level=3)

    if args.ncores is not None and args.ncores > 0:
        seamless.config.set_ncores(args.ncores)

    if args.direct_print:
        import seamless.workflow.core.execute

        seamless.workflow.core.execute.DIRECT_PRINT = True

    from seamless.workflow.core import context

    ctx = context(toplevel=True)

    loop = asyncio.get_event_loop()
    if args.time:
        loop.call_later(args.time, sys.exit)

    def raise_system_exit(*args, **kwargs):
        raise SystemExit

    signal.signal(signal.SIGTERM, raise_system_exit)
    signal.signal(signal.SIGHUP, raise_system_exit)
    signal.signal(signal.SIGINT, raise_system_exit)

    from seamless.workflow.core.manager import Manager

    _dummy_manager = Manager()

    server = JobSlaveServer(args.host, args.port)
    server.start()

    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
