import argparse
parser = argparse.ArgumentParser()
parser.add_argument("zipfile")
args = parser.parse_args()

import seamless
from seamless.core.cache.buffer_cache import buffer_cache
seamless.database_sink.connect()

from seamless.highlevel import Context
ctx = Context()
checksums = ctx.add_zip(args.zipfile, incref=True)
print("Added {} buffers".format(len(checksums)))
for checksum in checksums:
    buffer_cache.decref(bytes.fromhex(checksum))
