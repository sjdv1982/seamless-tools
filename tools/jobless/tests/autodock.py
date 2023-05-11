
import os
os.environ["SEAMLESS_COMMUNION_ID"] = "seamless"
from seamless.highlevel import Context, Cell, Transformer

import seamless
seamless.set_ncores(0)
from seamless import communion_server

communion_server.configure_master(
    transformation_job=True,
    transformation_status=True,
)

db_loghandle = open("jobless-test-dblog.txt", "a")
seamless.database_sink.connect()
seamless.database_sink.set_log(db_loghandle)
seamless.database_cache.connect()
seamless.database_cache.set_log(db_loghandle)
communion_server.start()

ctx = Context()
ctx.mol22pdb = Transformer()
ctx.mol22pdb.language = "bash"
ctx.mol22pdb.code.mount("mol22pdb.bash", authority="file")
ctx.mol22pdb.docker_image = "rpbs/autodock"
ctx.mol2 = Cell("text")
ctx.mol2.mount("1T4E_ligands.mol2", authority="file")
ctx.mol22pdb.mol2_file = ctx.mol2
ctx.result = ctx.mol22pdb
ctx.compute()
print(ctx.result.value)
print(ctx.mol22pdb.status)
print(ctx.mol22pdb.exception)
