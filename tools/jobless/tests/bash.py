
import os
os.environ["SEAMLESS_COMMUNION_ID"] = "seamless"
print("""Note: the final two tests assume that jobless is run in an 
environment with Numpy available.
Note that conda environments are not inherited from the shell that runs jobless!
""")
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

ctx = Context()
ctx.code = "head -$lines testdata > RESULT"
ctx.code.celltype = "text"
ctx.tf = lambda lines, testdata: None
ctx.tf.language = "bash"
ctx.tf.testdata = "a \nb \nc \nd \ne \nf \n"
ctx.tf.pins.testdata.celltype = "text"
ctx.tf.lines = 3
ctx.tf.code = ctx.code
ctx.result = ctx.tf
ctx.result.celltype = "mixed"
ctx.translate()
ctx.compute()
print(ctx.result.value)
print(ctx.tf.status)
print(ctx.tf.exception)
ctx.code = "head -3 testdata > firstdata; mkdir RESULT; cp testdata firstdata RESULT"
ctx.compute()
print(ctx.result.value)
print(ctx.tf.status)
print(ctx.tf.exception)
ctx.code = "python3 -c 'import numpy as np; np.save(\"test\",np.arange(12)*3)'; cat test.npy > RESULT"
ctx.compute()
print(ctx.tf.result.value)
print(ctx.tf.status)
print(ctx.tf.exception)
ctx.code = """
python3 -c 'import numpy as np; np.save(\"test\",np.arange(12)*3)'
echo 'hello' > test.txt
mkdir RESULT
cp test.npy test.txt RESULT
"""
ctx.result = ctx.tf
ctx.result.celltype = "structured"
ctx.result_npy = ctx.result["test.npy"]
ctx.result_txt = ctx.result["test.txt"]
ctx.compute()
print("")
print(ctx.result.value)
print(ctx.result_npy.value)
print(ctx.result_txt.value)
print(ctx.tf.status)
print(ctx.tf.exception)