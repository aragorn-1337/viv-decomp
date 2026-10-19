"""Core binary patching logic.

Byte-level patch representation so patches are independent of the compiler
AST. A ``BytePatch`` is a contiguous override at an offset; applying a patch
that doesn't match the original bytes fails (regression detection).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class BytePatch:
    """A contiguous byte override at a file offset.

    ``original`` must equal the current bytes at ``offset`` for the patch to
    apply cleanly (enables regression detection on re-application).
    """

    offset: int
    original: bytes
    replacement: bytes

    def __post_init__(self):
        if self.offset < 0:
            raise ValueError(f"Negative offset: {self.offset}")
        if not self.original or not self.replacement:
            raise ValueError("Patch bytes must be non-empty")
        if len(self.original) != len(self.replacement):
            raise ValueError("Patch original/replacement lengths must match")

    @property
    def size(self) -> int:
        return len(self.original)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"BytePatch(off=0x{self.offset:x}, "
                f"len={self.size}, "
                f"orig={self.original.hex()[:16]}..., "
                f"new={self.replacement.hex()[:16]}...)")


@dataclass
class PatchSet:
    """An ordered collection of BytePatches."""

    patches: List[BytePatch] = field(default_factory=list)
    source_desc: str = ""  # e.g. "diff from foo.c changes"

    def add(self, patch: BytePatch):
        self.patches.append(patch)

    def add_many(self, patches: List[BytePatch]):
        self.patches.extend(patches)

    def sort_by_offset(self):
        self.patches.sort(key=lambda p: p.offset)

    @property
    def count(self) -> int:
        return len(self.patches)

    @property
    def total_bytes(self) -> int:
        return sum(p.size for p in self.patches)

    def overlapping(self) -> List[tuple]:
        """Return pairs of patches that overlap the same byte range."""
        self.sort_by_offset()
        overlaps = []
        prev_end = -1
        prev = None
        for p in self.patches:
            if p.offset < prev_end:
                overlaps.append((prev, p))
            prev_end = p.offset + p.size
            prev = p
        return overlaps


def compute_diff(original: bytes, patched: bytes) -> List[BytePatch]:
    """Diff two binaries of equal length into BytePatches.

    Only contiguous runs where bytes changed become single patches. Returns
    [] if identical. Raises ValueError if lengths differ.
    """
    if len(original) != len(patched):
        raise ValueError(
            f"Length mismatch: original={len(original)} patched={len(patched)}"
        )
    patches: List[BytePatch] = []
    i = 0
    n = len(original)
    while i < n:
        if original[i] == patched[i]:
            i += 1
            continue
        # Start of a changed run
        start = i
        while i < n and original[i] != patched[i]:
            i += 1
        patches.append(BytePatch(
            offset=start,
            original=original[start:i],
            replacement=patched[start:i],
        ))
    return patches


def validate_patch(binary: bytes, patch: BytePatch) -> bool:
    """Check that the patch's original bytes match binary at its offset."""
    if patch.offset + patch.size > len(binary):
        return False
    return binary[patch.offset:patch.offset + patch.size] == patch.original


def apply_patches(binary: bytes, patches: List[BytePatch]) -> bytes:
    """Apply patches in order to a copy of ``binary``.

    Raises ValueError if a patch's original bytes don't match (regression
    detection / protection against stale patches).
    """
    out = bytearray(binary)
    for p in patches:
        if not validate_patch(binary, p):
            raise ValueError(
                f"Patch at offset 0x{p.offset:x} does not match original bytes "
                f"(stale or conflicting patch)"
            )
        out[p.offset:p.offset + p.size] = p.replacement
    return bytes(out)


class Patcher:
    """High-level patching workflow with regression detection."""

    def __init__(self):
        self.patch_sets: List[PatchSet] = []

    # ── Diffing ──

    def diff(self, original: bytes, patched: bytes) -> PatchSet:
        """Create a PatchSet from a before/after byte diff."""
        ps = PatchSet(source_desc="byte diff")
        ps.add_many(compute_diff(original, patched))
        self.patch_sets.append(ps)
        return ps

    def diff_from_files(self, original_path: str, patched_path: str) -> PatchSet:
        with open(original_path, "rb") as f:
            orig = f.read()
        with open(patched_path, "rb") as f:
            patched = f.read()
        return self.diff(orig, patched)

    # ── Apply ──

    def apply(self, binary: bytes, patches: List[BytePatch]) -> bytes:
        return apply_patches(binary, patches)

    # ── Regression detection ──

    def regression_check(self, patched_binary: bytes,
                         original_binary: bytes,
                         patches: List[BytePatch]) -> bool:
        """True if re-applying patches to the *patched* binary would fail.

        This detects whether patches have already been applied (idempotency).
        """
        # If the current binary already has all replacements, reapplying is
        # expected to fail -> that is NOT a corruption, just already-applied.
        already = True
        for p in patches:
            if patched_binary[p.offset:p.offset + p.size] != p.replacement:
                already = False
                break
        return already

    def summary(self, ps: PatchSet) -> str:
        lines = [f"PatchSet ({ps.source_desc or 'unspecified'}): "
                 f"{ps.count} patches, {ps.total_bytes} bytes"]
        for p in sorted(ps.patches, key=lambda x: x.offset):
            lines.append(f"  @0x{p.offset:08x} (+{p.size})")
        return "\n".join(lines)
