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


def _load_once(key: str, filename: str, proto_name: str = ""):
    """Load a proto module from *filename* once, cached under bare *key*.

    Robustness layers (in order):
    1. sys.modules hit  — bare key survives MP hot-reload; just return it.
    2. Pre-scan         — another key in sys.modules already holds the same
                          file (e.g. full package path from an older code
                          version); alias it under the bare key and return.
    3. Normal load      — exec the file; register under bare key.
    4. Duplicate error  — AddSerializedFile raised because the descriptor
                          pool already has this file from a prior load in
                          this process.  Steps:
       4a. Post-scan    — try to find a complete module (has DESCRIPTOR)
                          from sys.modules loaded from the same file.
       4b. Reconstruct  — use the pool's existing FileDescriptor plus
                          protobuf's Builder to recreate the message classes
                          on a fresh module object, so callers get a fully
                          usable pb2 module without ever re-running
                          AddSerializedFile.
    """
    if key in sys.modules:
        return sys.modules[key]

    filepath = _HERE / filename

    # 1→2. Pre-scan: find module already loaded from the same file.
    existing = _find_by_file(filepath)
    if existing is not None:
        sys.modules[key] = existing
        return existing

    # 3. Normal load.
    spec = importlib.util.spec_from_file_location(key, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod  # register before exec so self-references resolve
    try:
        spec.loader.exec_module(mod)
        return mod
    except RuntimeError as exc:
        if "duplicate" not in str(exc).lower():
            del sys.modules[key]
            raise

    # 4. Duplicate: descriptor pool already has this file from a prior load.
    del sys.modules[key]

    # 4a. Post-scan: find a complete module from sys.modules.
    complete = _find_by_file(filepath)
    if complete is not None and hasattr(complete, "DESCRIPTOR"):
        sys.modules[key] = complete
        return complete

    # 4b. Reconstruct: build message classes using the pool's FileDescriptor.
    if proto_name:
        try:
            from google.protobuf import descriptor_pool as _dp
            from google.protobuf.internal import builder as _b
            file_desc = _dp.Default().FindFileByName(proto_name)
            # mod already has __name__ / __file__ set; populate pb2 symbols.
            _b.BuildMessageAndEnumDescriptors(file_desc, vars(mod))
            _b.BuildTopDescriptorsAndMessages(file_desc, key, vars(mod))
            mod.DESCRIPTOR = file_desc
            sys.modules[key] = mod
            return mod
        except Exception:
            pass

    # All layers failed — raise so the outer except logs the real error.
    raise RuntimeError(
        f"Couldn't load proto module '{filename}': descriptor pool already "
        f"contains the file but no usable module could be recovered."
    )


cd2_pb2 = _load_once("cd2_pb2", "cd2_pb2.py", proto_name="cd2.proto")
cd2_pb2_grpc = _load_once("cd2_pb2_grpc", "cd2_pb2_grpc.py")
