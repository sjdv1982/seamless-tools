import asyncio
import os
import signal
import socket
import sys
import traceback
from aiohttp import web
from seamless.highlevel import Checksum

def is_port_in_use(address, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((address, port)) == 0

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
            checksum = Checksum(data["checksum"])
            dunder = data["dunder"]
            task = asyncio.create_task(seamless.run_transformation_async(checksum.bytes(), fingertip=True, tf_dunder=dunder))
            try:
                result = await asyncio.wait_for(asyncio.shield(task), timeout=10.0)
            except asyncio.TimeoutError:
                return web.Response(status=202) # just send it again, later

            #print("RESULT!", result.hex() if result is not None else None)
            if result is not None:
                result = result.hex()
                return web.Response(
                    status=200,
                    body=result
                )
            return web.Response(
                status=400,
                body="ERROR: Unknown error"
            )            
        except Exception as exc:
            traceback.print_exc()
            return web.Response(
                status=400,
                body="ERROR: " + str(exc)
            )

    
if __name__ == "__main__":
    import argparse
    env = os.environ
    parser = argparse.ArgumentParser(description="""Simple assistant.
""")
    parser.add_argument("--time",type=float,default=None)
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
        help="Verbose mode, setting the Seamless logger to INFO",
        action="store_true"
    )
    parser.add_argument(
        "--debug",
        help="Debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
        action="store_true"
    )

    args = parser.parse_args()
    if args.port == -1:
        raise ValueError("Network port is not defined, neither as --port nor as SEAMLESS_ASSISTANT_PORT variable")

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

    seamless.config.delegate(level=3)

    if args.ncores is not None and args.ncores > 0:
        seamless.set_ncores(args.ncores)

    if args.direct_print:
        import seamless.core.execute
        seamless.core.execute.DIRECT_PRINT = True

    from seamless.core import context
    ctx = context(toplevel=True)

    loop = asyncio.get_event_loop()
    if args.time:
        loop.call_later(args.time, sys.exit)

    def raise_system_exit(*args, **kwargs):
        raise SystemExit
    
    signal.signal(signal.SIGTERM, raise_system_exit)
    signal.signal(signal.SIGHUP, raise_system_exit)
    signal.signal(signal.SIGINT, raise_system_exit)

    server = JobSlaveServer(args.host, args.port)
    server.start()

    from seamless.core.transformation import get_global_info, execution_metadata0
    from seamless.core.cache.transformation_cache import transformation_cache
    transformation_cache.stateless = True
    
    get_global_info()
    execution_metadata0["Executor"] = "micro-assistant"

    if not args.interactive:
        print("Press Ctrl+C to end")
        loop.run_forever()
