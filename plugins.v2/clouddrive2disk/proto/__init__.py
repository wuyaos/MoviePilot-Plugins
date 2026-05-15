# input: none
# output: cd2_pb2, cd2_pb2_grpc modules
# pos: proto package for CloudDrive2Disk; loads proto modules once under bare sys.modules
#      keys that survive MoviePilot hot-reload cleanup (MP only removes app.plugins.* entries).
#      cd2_pb2_grpc.py uses `import cd2_pb2` (bare absolute import), so the bare key
#      must exist in sys.modules before cd2_pb2_grpc is executed.
#      cd2_pb2.py itself handles AddSerializedFile duplicate errors (recovers via
#      FindFileByName), so exec_module here always either succeeds or raises non-duplicate.

import sys
import importlib.util
from pathlib import Path

_HERE = Path(__file__).parent


def _find_by_file(filepath: Path):
    """Return the first sys.modules entry whose __file__ resolves to *filepath*."""
    resolved = str(filepath.resolve())
    for mod in list(sys.modules.values()):
        try:
            mf = getattr(mod, "__file__", None)
            if mf and str(Path(mf).resolve()) == resolved:
                return mod
        except Exception:
            pass
    return None


def _load_once(key: str, filename: str, sentinel: str = ""):
    """Load a proto module from *filename* once, cached under bare *key*.

    Robustness layers (in order):
    1. sys.modules hit  — bare key survives MP hot-reload; just return it.
                          If *sentinel* is given, verify the cached module
                          actually has that attribute; if not, the entry is
                          a stale incomplete module (left by an older code
                          version's failed reconstruct) — evict and reload.
    2. Pre-scan         — another key in sys.modules already holds the same
                          file (e.g. full package path from an older code
                          version); alias it under the bare key and return.
    3. Normal load      — exec the file; cd2_pb2.py handles AddSerializedFile
                          duplicate internally via FindFileByName, so exec
                          always returns a fully-initialised module.
    """
    if key in sys.modules:
        mod = sys.modules[key]
        if not sentinel or hasattr(mod, sentinel):
            return mod
        # Cached module is incomplete (missing sentinel attr) — evict it.
        del sys.modules[key]

    filepath = _HERE / filename

    # Layer 2: pre-scan — find module already loaded from the same file.
    existing = _find_by_file(filepath)
    if existing is not None:
        sys.modules[key] = existing
        return existing

    # Layer 3: normal load.
    spec = importlib.util.spec_from_file_location(key, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # register before exec so self-references resolve
    try:
        spec.loader.exec_module(mod)
    except Exception:
        del sys.modules[key]
        raise
    return mod


cd2_pb2 = _load_once("cd2_pb2", "cd2_pb2.py", sentinel="GetTokenRequest")
cd2_pb2_grpc = _load_once("cd2_pb2_grpc", "cd2_pb2_grpc.py")
