import os
os.environ["SEAMLESS_COMMUNION_ID"] = "seamless"
from seamless.highlevel import Context

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

def count_atoms(pdbdata):
    from Bio.PDB import PDBParser
    parser = PDBParser()
    from io import StringIO
    d = StringIO(pdbdata)
    struc = parser.get_structure("pdb", d)
    return len(list(struc.get_atoms()))

ctx = Context()
ctx.pdbdata = open("1crn.pdb").read()
ctx.count_atoms = count_atoms
ctx.count_atoms.pdbdata = ctx.pdbdata
ctx.count_atoms.pins.pdbdata.celltype = "text"
ctx.count_atoms.environment.set_conda(
    open("parse-pdb-environment.yml").read(),
    "yaml"
)
ctx.compute()
print(ctx.count_atoms.get_transformation())
print(ctx.count_atoms.status)
print(ctx.count_atoms.exception)
print(ctx.count_atoms.result.value)