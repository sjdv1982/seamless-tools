import sys
import seamless
from seamless.highlevel import Checksum
from seamless.core.manager.expression import Expression
from seamless.core.manager.tasks.evaluate_expression import build_expression_transformation

checksum = Checksum(sys.argv[1])
# WIP tool to re-evaluate expressions with run-transformation

path = []
celltype = "mixed"
target_celltype = "mixed"
hash_pattern = None
if "--deep" in sys.argv:
    hash_pattern = {"*": "#"}
target_hash_pattern = None

expression = Expression(
        checksum.bytes(), path, celltype,
        target_celltype, None,
        hash_pattern=hash_pattern, target_hash_pattern=target_hash_pattern
)
print(expression)       
print(build_expression_transformation(expression).hex()) 