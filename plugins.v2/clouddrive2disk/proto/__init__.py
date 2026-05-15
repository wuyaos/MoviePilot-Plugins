# input: none
# output: cd2_pb2, cd2_pb2_grpc modules
# pos: proto package for CloudDrive2Disk; loads proto modules once under bare sys.modules
#      keys that survive MoviePilot hot-reload cleanup (MP only removes app.plugins.* entries).
#      cd2_pb2_grpc.py uses `import cd2_pb2` (bare absolute import), so the bare key
#      must exist in sys.modules before cd2_pb2_grpc is executed.

import sys
import importlib.util
from pathlib import Path

_HERE = Path(__file__).parent


def _load_once(key: str, filename: str):
    """Load a module from file once and cache under `key` in sys.modules.

    On MoviePilot hot-reload MP clears `app.plugins.*` from sys.modules but
    never touches bare names like ``cd2_pb2``.  Subsequent calls therefore
    return the already-loaded module without calling AddSerializedFile again,
    preventing the ``duplicate extension entry`` descriptor-pool error.
    """
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, _HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # register before exec so self-references resolve
    spec.loader.exec_module(mod)
    return mod


cd2_pb2 = _load_once("cd2_pb2", "cd2_pb2.py")
cd2_pb2_grpc = _load_once("cd2_pb2_grpc", "cd2_pb2_grpc.py")
