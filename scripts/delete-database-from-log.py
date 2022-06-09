import sys
import seamless

import argparse
parser = argparse.ArgumentParser()
parser.add_argument(
    "logfile",
    help="""Seamless database log file.
Should have been generated with seamless.database_cache.set_log 
and/or seamless.database_sink.set_log.
All entries in the log will be deleted from the database.
""",
    type=argparse.FileType('r')
)
args = parser.parse_args()

cache = seamless.database_cache
cache.connect()

entries = set()
for l in args.logfile:
    ll = l.split()
    if not len(ll):
        continue
    type, checksum = ll
    entries.add((type, checksum))

for type, checksum in entries:
    cs = bytes.fromhex(checksum)
    deleted = cache.delete_key(type, cs)
    result = "DELETED" if deleted else "NOT_FOUND"
    print(result, type, checksum)
