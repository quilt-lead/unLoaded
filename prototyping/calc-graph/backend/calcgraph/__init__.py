"""calc-graph backend: IFC + calc package ingest, mapping, revision store, API."""
from . import store_root as _store_root

ENGINE_VERSION = "mapper-v1.0"

# Any process that imports calcgraph (the server, every script, the tests, the generator) refuses writes
# into the source data dirs unless inside store_root.allow_source_writes() - see store_root.py.
_store_root.install_source_write_guard()
