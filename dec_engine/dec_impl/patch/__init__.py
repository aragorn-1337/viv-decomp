"""Binary patching utilities (S8).

Provides byte-level patch diff generation + application from decompiled-code
changes:

- ``BytePatch``: a single contiguous byte override at a file offset
- ``compute_diff``: diff two binaries (original vs patched) into BytePatches
- ``apply_patches``: apply patches to a binary
- ``Patcher``: high-level wrapper with regression detection
"""
from dec_engine.dec_impl.patch.core import (
    BytePatch,
    PatchSet,
    compute_diff,
    apply_patches,
    Patcher,
    validate_patch,
)

__all__ = [
    "BytePatch",
    "PatchSet",
    "compute_diff",
    "apply_patches",
    "Patcher",
    "validate_patch",
]
