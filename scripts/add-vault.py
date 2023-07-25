import argparse
import os
import sys
parser = argparse.ArgumentParser()
parser.add_argument("vault_directory")
parser.add_argument("--flat", action="store_true", help="Directory is a flat directory containing checksum-named buffer files")
args = parser.parse_args()

import seamless
from seamless.core.cache.buffer_cache import buffer_cache
from seamless.vault import load_vault, load_vault_flat
seamless.database_sink.connect()

try:
    vault = args.vault_directory
    if not os.path.exists(vault):
        raise ValueError("Vault directory does not exist")
    if not os.path.isdir(vault):
        raise ValueError("Vault directory is not a directory")

    if args.flat:
        checksums = load_vault_flat(vault, incref=True)
    else:
        try:
            checksums = load_vault(vault, incref=True)
        except ValueError as exc:
            if exc.args[0].find("vault") > -1:
                msg = """This directory is not a canonical vault directory.
It does not contain subdirectories /independent/small, /dependent/big, etc.
If the directory contains flat checksum-named buffer files,
  (i.e. a /buffers/ subdirectory of a Seamless database dir,
    or an unzipped Seamless .zip file),
 then use the --flat option.
"""
                raise ValueError(msg) from None
    print("Added {} buffers".format(len(checksums)))
    for checksum in checksums:
        buffer_cache.decref(bytes.fromhex(checksum))
except ValueError:
    import traceback
    traceback.print_exc(0)
    sys.exit(1)