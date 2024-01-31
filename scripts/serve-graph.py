import sys, os, json, subprocess, argparse
parser = argparse.ArgumentParser()
parser.add_argument(
    "graph",
    help="Seamless graph file to serve",
    type=argparse.FileType('r')
)

parser.add_argument(
    "--delegate",
    help="""Delegate all computation and buffer storage to remote servers/folders.
These servers/folders are read from environment variables.    
Optionally, a delegation level can be provided (default: 4)
See the documentation of seamless.delegate(...) for more details.""",
    nargs="?",
    type=int,
    default=0,
    const=4
)

parser.add_argument(
    "--interactive",
    help="Do not enter a mainloop. Assumes that the script was opened with an interactive shell (e.g. ipython -i)",
    action="store_true"
)
parser.add_argument(
    "--debug",
    help="Serve graph in debugging mode. Turns on asyncio debugging, and sets the Seamless logger to DEBUG",
    action="store_true"
)

parser.add_argument(
    "--status-graph",
    help="""Bind a graph that reports the status of the main graph. 
Optionally, provide a .seamless file, else the default status visualization graph is used.""",
    nargs="?",
    const="/seamless-graphs/status-visualization.seamless"
)

parser.add_argument(
    "--load-zip",
    help="Specify additional zip files to be loaded as buffer sources",
    dest="zips",
    nargs="*",
    action="append",
    default=[],
)

parser.add_argument(
    "--load-vault",
    help="Specify additional vault folders to be loaded as buffer sources",
    dest="vaults",
    nargs="*",
    action="append",
    default=[],
)

parser.add_argument("--ncores",type=int,default=None)

parser.add_argument(
    "--no-shares",
    dest="no_shares",
    help="Don't share cells over the network as specified in the graph file(s)",
    action="store_true",
)

parser.add_argument(
    "--mounts",
    help="Mount cells on the file system as specified in the graph file(s)",
    action="store_true",
)

parser.add_argument(
    "--no-lru",
    dest="no_lru",
    help="Disable LRU caches for checksum-to-buffer, value-to-checksum, value-to-buffer, and buffer-to-value",
    action="store_true"
)

args = parser.parse_args()
zips = []
for zipl in args.zips:
    for zipf in zipl:
        zips.append(zipf)

if args.status_graph == "/seamless-graphs/status-visualization.seamless":
    zipf = "/seamless-graphs/status-visualization.zip"
    if zipf not in zips:
        zips.append(zipf)


vaults = []
for vaultl in args.vaults:
    for vault in vaultl:
        vaults.append(vault)

if not args.delegate and not zips and not vaults:
    print("No buffer sources have been defined. Consider adding --delegate", file=sys.stderr)
    sys.exit(1)

if args.debug:
    import asyncio
    asyncio.get_event_loop().set_debug(True)
    import logging
    logging.basicConfig()
    logging.getLogger("seamless").setLevel(logging.DEBUG)

env = os.environ

import seamless

delegation_error = seamless.delegate(args.delegate)
if delegation_error:
    exit(1)
if args.status_graph or args.ncores:
    seamless.config.unblock_local()

if args.no_lru:
    from seamless.core.protocol.calculate_checksum import calculate_checksum_cache, checksum_cache
    from seamless.core.protocol.deserialize import deserialize_cache
    from seamless.core.protocol.serialize import serialize_cache
    calculate_checksum_cache.disable()
    checksum_cache.disable()
    deserialize_cache.disable()
    serialize_cache.disable()

import seamless.shareserver

if args.ncores is not None:
    seamless.set_ncores(args.ncores)

if not args.no_shares:
    shareserver_address = env.get("SHARESERVER_ADDRESS")
    if shareserver_address is not None:
        if shareserver_address == "HOSTNAME":
            shareserver_address = subprocess.getoutput("hostname -I | awk '{print $1}'")
        seamless.shareserver.DEFAULT_ADDRESS = shareserver_address
        print("Setting shareserver address to: {}".format(shareserver_address))

import seamless.highlevel.stdlib

from seamless.highlevel import load_graph, Context
graph = json.load(args.graph)
if args.delegate == 4:
    for node in graph.get("nodes", []):
        if node.get("type") == "transformer":
            meta = node.get("meta")
            if meta is not None:
                meta.pop("local", None)
ctx = Context()
for zipf in zips:
    ctx.add_zip(zipf)
for vault in vaults:
    ctx.load_vault(vault)
ctx.set_graph(graph, mounts=args.mounts, shares=(not args.no_shares))
ctx.translate()

if args.status_graph:
    from seamless.metalevel.bind_status_graph import bind_status_graph
    with open(args.status_graph) as f:
        status_graph = json.load(f)
    if args.delegate and (args.ncores is None or int(args.ncores)):
        for node in status_graph.get("nodes", []):
            if node.get("type") == "transformer":
                meta = node.get("meta", {})
                meta["local"] = True
                node["meta"] = meta
    webctx = bind_status_graph(
        ctx, status_graph,
        mounts=False,
        shares=True,
        zips=zips,
    )

print("Serving graph...")
if not args.interactive:
    print("Press Ctrl+C to end")
    import asyncio
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass