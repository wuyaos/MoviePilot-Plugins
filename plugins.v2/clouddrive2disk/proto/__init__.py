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


def _load_once(key: str, filename: str):
    """Load a module from file once and cache under *key* in sys.modules.

    Why bare keys survive MP hot-reload:
      MoviePilot clears ``app.plugins.*`` entries from sys.modules on reload,
      but never touches bare names like ``"cd2_pb2"``.  Once loaded, the module
      stays cached and AddSerializedFile is never called a second time.

    Extra robustness layers:
      1. Pre-scan: if the file is already loaded under a *different* key
         (e.g., the full package path from an older code version), reuse it.
      2. Post-duplicate scan: if exec_module raises the ``duplicate extension
         entry`` RuntimeError (pool already has the descriptor from an earlier
         load in this process), look for a complete, usable module instance
         (one that has a ``DESCRIPTOR`` attribute) in sys.modules rather than
         returning a half-initialised module.
    """
    if key in sys.modules:
        return sys.modules[key]

    filepath = _HERE / filename

    # 1. Pre-scan: find a module already loaded from the same file.
    existing = _find_by_file(filepath)
    if existing is not None:
        sys.modules[key] = existing
        return existing

    spec = importlib.util.spec_from_file_location(key, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # register before exec so self-references resolve
    try:
        spec.loader.exec_module(mod)
    except RuntimeError as exc:
        if "duplicate" not in str(exc).lower():
            del sys.modules[key]
            raise
        # 2. Post-duplicate scan: descriptor pool already has this file from a
        #    prior load that was removed from sys.modules.  The module we just
        #    exec'd is incomplete (message classes not built).  Try to find a
        #    complete instance (has DESCRIPTOR) that was loaded from the same file.
        del sys.modules[key]
        complete = _find_by_file(filepath)
        if complete is not None and hasattr(complete, "DESCRIPTOR"):
            sys.modules[key] = complete
            return complete
        # No usable instance found; re-raise so the outer try/except logs it.
        raise
    return mod


cd2_pb2 = _load_once("cd2_pb2", "cd2_pb2.py")
cd2_pb2_grpc = _load_once("cd2_pb2_grpc", "cd2_pb2_grpc.py")
