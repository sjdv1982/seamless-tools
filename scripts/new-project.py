import sys, os, shutil, json
import seamless
os.environ["SEAMLESS_SILENT"] = "1"
seamless.delegate(False)
from seamless.highlevel import Context
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "project_name",
    help="Name of the project",
)
args = parser.parse_args()
project_name = args.project_name

def pr(*args):
    print(*args, file=sys.stderr)

notebook = r"""{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "metadata": {
    "collapsed": true
   },
   "outputs": [],
   "source": [
    "%run -i load-project.py\n",
    "await load()"
   ]
  }
 ],
 "metadata": {},
 "nbformat": 4,
 "nbformat_minor": 2
}"""

subpaths = [
    "web",
    "graph",
    "vault"
]
for subpath in subpaths:
    if os.path.exists(subpath):
        pr("%s/ already exists, aborting..." % subpath)
        exit(1)

for subpath in subpaths:
    os.mkdir(subpath)

import seamless
seamless_dir = os.path.dirname(seamless.__file__)

empty = Context()
empty.save_graph("graph/{0}.seamless".format(project_name))
del empty

f = "webgen.seamless"
source = os.path.join(seamless_dir, "graphs", f)
dest = os.path.join("graph", "{0}-webctx.seamless".format(project_name))
shutil.copy(source, dest)
graph = json.load(open(dest))

ctx = Context()
ctx.add_zip(os.path.join(seamless_dir, "graphs", "webgen.zip"))
ctx.set_graph(graph)
ctx.save_vault("vault")

gitignore = """# Seamless vault files and backups

# 1. Independent, big buffers. Uncomment the following line to remove them from version control
### vault/independent/big/*

# 2. Dependent, big buffers. Comment out the following line to put them under version control
vault/dependent/big/*

# 3. Dependent, small buffers. Comment out the following line to put them under version control
vault/dependent/small/*

# 4. Backups of the Seamless graph. Comment out the following line to put them under version control
graph/*.seamless.bak*

# In all cases, at least keep an empty directory for the vaults
!vault/*/*/.gitkeep

"""

if os.path.exists(".gitignore"):
    pr(".gitignore file already exists. Adding Seamless entries...")
    with open(".gitignore", "a") as f:
        f.write("\n" + gitignore)
else:
    with open(".gitignore", "w") as f:
        f.write(gitignore)

code = '''
PROJNAME = "{project_name}"

DELEGATION_LEVEL = 0

"""
Change DELEGATION_LEVEL to the appropriate level:

DELEGATION_LEVEL = 0
Runs load_vault on project startup
Runs save_vault on project save.
All input/output buffers and results are held in memory.

DELEGATION_LEVEL = 1
External read buffer servers/folders may be configured. 
On project startup, run load_vault if vault/ exists.
On project save, run save_vault if vault/ exists

DELEGATION_LEVEL = 2
Buffers are stored in an external buffer server. 
Such a server can be launched using "seamless-delegate none"
Vaults are being ignored on project load/save. You are recommended to upload the vault/ directory 
using "seamless-upload"

DELEGATION_LEVEL = 3
Buffers are stored in an external buffer server.
Results are stored as checksums in a database server.
Such servers can be launched using "seamless-delegate none"
Vaults are being ignored on project load/save. You are recommended to upload the vault/ directory 
using "seamless-upload"

DELEGATION_LEVEL = 4
All jobs, buffers and results are delegated to an external assistant
Such an assistant can be launched using "seamless-delegate <name of assistant>" 
Vaults are being ignored on project load/save. You are recommended to upload the vault/ directory 
using "seamless-upload"
"""

import os, sys, shutil

import seamless
seamless.delegate(DELEGATION_LEVEL)

from seamless.highlevel import Context, Cell, Transformer, Module, Macro

ctx = None
webctx = None
save = None
export = None

def pr(*args):
    print(*args, file=sys.stderr)

async def define_graph(ctx):
    """Code to define the graph
    Leave this function empty if you want load() to load the graph from graph/PROJNAME.seamless 
    """
    pass

def load_ipython():
    import asyncio
    import seamless
    loop = seamless._original_event_loop
    asyncio.set_event_loop(loop)
    coro = load()
    loop.run_until_complete(coro)

async def load():
    from seamless.metalevel.bind_status_graph import bind_status_graph_async
    import json

    global ctx, webctx, save, export

    try:
        ctx
    except NameError:
        pass
    else:
        if ctx is not None:
            pr('"ctx" already exists. To reload, do "ctx = None" or "del ctx" before "await load()"')
            return

    for f in (
        "web/index-CONFLICT.html",
        "web/index-CONFLICT.js",
        "web/webform-CONFLICT.txt",
    ):
        if os.path.exists(f):
            try:
                if open(f).read().rstrip("\\n ") in ("", "No conflict"):
                    continue
            except UnicodeDecodeError:
                continue
            dest = f + "-BAK"
            if os.path.exists(dest):
                os.remove(dest)            
            pr("Existing '{{}}' found, moving to '{{}}'".format(f, dest))
            shutil.move(f, dest)
    ctx = Context()
    empty_graph = ctx.get_graph()
    try:
        seamless._defining_graph = True
        await define_graph(ctx)
    finally:
        try:
            del seamless._defining_graph
        except AttributeError:
            pass
    new_graph = ctx.get_graph()
    graph_file = "graph/" + PROJNAME + ".seamless"
    if DELEGATION_LEVEL == 0: 
        ctx.load_vault("vault")
    elif DELEGATION_LEVEL == 1:
        if os.path.exists("vault"):
            ctx.load_vault("vault")
    if new_graph != empty_graph:
        pr("*** define_graph() function detected. Not loading '{{}}'***\\n".format(graph_file))
    else:
        pr("*** define_graph() function is empty. Loading '{{}}' ***\\n".format(graph_file))
        graph = json.load(open(graph_file))        
        ctx.set_graph(graph, mounts=True, shares=True)
        await ctx.translation(force=True)

    status_graph = json.load(open("graph/" + PROJNAME + "-webctx.seamless"))

    webctx = await bind_status_graph_async(
        ctx, status_graph,
        mounts=True,
        shares=True
    )
    
    def save():
        import os, itertools, shutil

        def backup(filename):
            if not os.path.exists(filename):
                return filename
            for n in itertools.count():
                n2 = n if n else ""
                new_filename = "{{}}.bak{{}}".format(filename, n2)
                if not os.path.exists(new_filename):
                    break
            shutil.move(filename, new_filename)
            return filename

        try:
            ctx.translate()
        except Exception:
            pass
        ctx.save_graph(backup("graph/" + PROJNAME + ".seamless"))
        try:
            webctx.translate()
        except Exception:
            pass        
        webctx.save_graph(backup("graph/" + PROJNAME + "-webctx.seamless"))
        if DELEGATION_LEVEL == 0: 
            ctx.save_vault("vault")
            webctx.save_vault("vault")
        elif DELEGATION_LEVEL == 1:
            if os.path.exists("vault"):
                ctx.save_vault("vault")
                webctx.save_vault("vault")

    def export():
        filename = "graph/{project_name}.zip"
        ctx.save_zip(filename)
        pr(f"{{filename}} saved")
        filename = "graph/{project_name}-webctx.zip"
        webctx.save_zip(filename)
        pr(f"{{filename}} saved")

    await ctx.translation(force=True)
    await ctx.translation(force=True)
    
    pr("""Project loaded.

    Main context is "ctx"
    Web/status context is "webctx"

    Open http://localhost:<REST server port> to see the web page
    Open http://localhost:<REST server port>/status/status.html to see the status

    Run save() to save the project workflow file.
    Run export() to generate zip files for web deployment.
    """)
'''.format(project_name=project_name)

with open("load-project.py", "w") as f:
    f.write(code)

with open("{0}.ipynb".format(project_name), "w") as f:
    f.write(notebook)

pr("""Project {0} created.

- Use seamless-load-project to start up IPython
or:
- Use seamless-jupyter to start up Jupyter
  and in the Jupyter browser window,
  open /home/jovyan/cwd/{0}.ipynb

If Seamless does not need to execute Docker transformers:
- Use seamless-load-project-safe to start up IPython
or:
- Use seamless-jupyter-safe to start up Jupyter
  and in the Jupyter browser window,
  open /home/jovyan/cwd/{0}.ipynb
""".format(project_name))