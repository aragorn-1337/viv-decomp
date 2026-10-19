"""Tests for the binary patching module (S8)."""
import sys, os, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dec_engine.dec_impl.patch import (
    BytePatch, PatchSet, compute_diff, apply_patches, Patcher, validate_patch,
)


def _bin(*vals):
    return bytes(vals)


class TestBytePatch:
    def test_construct(self):
        p = BytePatch(offset=0x100, original=b"\x00\x01", replacement=b"\xff\xfe")
        assert p.offset == 0x100
        assert p.size == 2

    def test_negative_offset_raises(self):
        with pytest.raises(ValueError):
            BytePatch(-1, b"\x00", b"\xff")

    def test_empty_bytes_raises(self):
        with pytest.raises(ValueError):
            BytePatch(0, b"", b"\xff")
        with pytest.raises(ValueError):
            BytePatch(0, b"\x00", b"")

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            BytePatch(0, b"\x00\x01", b"\xff")

    def test_repr(self):
        p = BytePatch(0x10, b"\x00", b"\xff")
        assert "0x10" in repr(p)


class TestPatchSet:
    def test_add_and_count(self):
        ps = PatchSet()
        ps.add(BytePatch(0, b"\x00", b"\xff"))
        ps.add(BytePatch(1, b"\x01", b"\x02"))
        assert ps.count == 2

    def test_total_bytes(self):
        ps = PatchSet()
        ps.add_many([BytePatch(0, b"\x00\x01", b"\xff\xfe"),
                     BytePatch(5, b"\x0a", b"\x0b")])
        assert ps.total_bytes == 3

    def test_sort_by_offset(self):
        ps = PatchSet()
        ps.add(BytePatch(10, b"\x00", b"\xff"))
        ps.add(BytePatch(0, b"\x00", b"\xff"))
        ps.sort_by_offset()
        assert ps.patches[0].offset == 0

    def test_overlapping_detection(self):
        ps = PatchSet()
        p1 = BytePatch(0, b"\x00\x01\x02", b"\xff\xfe\xfd")
        p2 = BytePatch(2, b"\x03", b"\x04")  # overlaps p1 (ends at 3)
        ps.add_many([p1, p2])
        assert len(ps.overlapping()) == 1


class TestComputeDiff:
    def test_identical_returns_empty(self):
        assert compute_diff(b"\x01\x02\x03", b"\x01\x02\x03") == []

    def test_single_run(self):
        patches = compute_diff(b"\x01\x02\x03", b"\x01\xff\x03")
        assert len(patches) == 1
        assert patches[0].offset == 1
        assert patches[0].replacement == b"\xff"

    def test_two_runs(self):
        patches = compute_diff(b"\x01\x02\x03\x04", b"\xff\x02\x03\xee")
        assert len(patches) == 2

    def test_contiguous_run_single_patch(self):
        patches = compute_diff(b"\x00\x01\x02", b"\xff\xfe\xfd")
        assert len(patches) == 1
        assert patches[0].replacement == b"\xff\xfe\xfd"

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            compute_diff(b"\x00\x01", b"\x00")

    def test_roundtrip_diff_apply(self):
        orig = _bin(1, 2, 3, 4, 5, 6)
        new = _bin(1, 9, 9, 4, 8, 6)
        patches = compute_diff(orig, new)
        result = apply_patches(orig, patches)
        assert result == new


class TestValidateAndApply:
    def test_validate_ok(self):
        p = BytePatch(1, b"\x02\x03", b"\xff\xff")
        assert validate_patch(b"\x01\x02\x03\x04", p) is True

    def test_validate_mismatch(self):
        p = BytePatch(1, b"\x99\x03", b"\xff\xff")
        assert validate_patch(b"\x01\x02\x03\x04", p) is False

    def test_validate_out_of_range(self):
        p = BytePatch(10, b"\xff", b"\x00")
        assert validate_patch(b"\x00", p) is False

    def test_apply_patches(self):
        orig = _bin(1, 2, 3, 4)
        patches = [BytePatch(1, b"\x02", b"\xff")]
        result = apply_patches(orig, patches)
        assert result == _bin(1, 255, 3, 4)

    def test_apply_stale_patch_raises(self):
        orig = _bin(1, 2, 3, 4)
        patches = [BytePatch(1, b"\x09", b"\xff")]  # original not 0x02
        with pytest.raises(ValueError):
            apply_patches(orig, patches)

    def test_apply_preserves_original(self):
        orig = _bin(1, 2, 3, 4)
        chunks = [b"AA", b"BB"]
        _ = chunks
        patches = [BytePatch(0, orig, _bin(9, 9, 9, 9))]
        apply_patches(orig, patches)
        assert orig == _bin(1, 2, 3, 4)  # immutable; original untouched


class TestPatcher:
    def test_diff(self):
        patcher = Patcher()
        ps = patcher.diff(b"\x01\x02\x03", b"\x01\xff\x03")
        assert ps.count == 1
        assert patcher.patch_sets == [ps]

    def test_diff_from_strings_roundtrip(self):
        patcher = Patcher()
        orig = b"hello world patch"
        patched = b"hello WORid patch"
        ps = patcher.diff(orig, patched)
        result = patcher.apply(orig, ps.patches)
        assert result == patched

    def test_regression_already_applied(self):
        patcher = Patcher()
        orig = b"\x00\x01\x02"
        patched = b"\xff\x01\x02"
        ps = patcher.diff(orig, patched)
        # patched already has the replacement -> regression_check True
        assert patcher.regression_check(patched, orig, ps.patches) is True

    def test_regression_not_applied(self):
        patcher = Patcher()
        orig = b"\x00\x01\x02"
        ps = patcher.diff(orig, b"\xff\x01\x02")
        # an unpatched binary that does NOT have replacement
        other = b"\x00\x01\xff"
        assert patcher.regression_check(other, orig, ps.patches) is False

    def test_summary_contains_patch_count(self):
        patcher = Patcher()
        ps = patcher.diff(b"\x00\x01\x02", b"\xff\x01\x02")
        s = patcher.summary(ps)
        assert "1 patches" in s
        assert "0x" in s


class TestPatchAsPlugin:
    def test_discoverable_via_plugin_system(self):
        from dec_engine.dec_impl.plugin import PluginRegistry
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir])
        assert reg.has_pass("patch_emitter")

    def test_emits_patch_set_from_metadata(self):
        from dec_engine.dec_impl.plugin import PluginRegistry
        from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir])
        entry = BasicBlock(addr=0x1000, is_entry=True)
        g = BlockGraph(entry_block=entry, blocks={0x1000: entry})
        g.metadata["original_bytes"] = b"\x00\x01\x02"
        g.metadata["patched_bytes"] = b"\xff\x01\x02"
        out = reg.run_passes(g, ["patch_emitter"])
        ps = out.metadata["patch_set"]
        assert ps.count == 1
        assert ps.patches[0].replacement == b"\xff"

    def test_patch_emitter_roundtrip_via_patcher(self):
        from dec_engine.dec_impl.plugin import PluginRegistry
        from dec_engine.dec_impl.ir.block import BasicBlock, BlockGraph
        from dec_engine.dec_impl.patch import Patcher
        reg = PluginRegistry()
        demo_dir = os.path.join(os.path.dirname(__file__), "plugins_demo")
        reg.discover_from([demo_dir])
        entry = BasicBlock(addr=0x1000, is_entry=True)
        g = BlockGraph(entry_block=entry, blocks={0x1000: entry})
        g.metadata["original_bytes"] = b"original thing here"
        g.metadata["patched_bytes"] = b"original thing gone"
        out = reg.run_passes(g, ["patch_emitter"])
        ps = out.metadata["patch_set"]
        patcher = Patcher()
        result = patcher.apply(g.metadata["original_bytes"], ps.patches)
        assert result == g.metadata["patched_bytes"]


class TestPatchFiles:
    def test_diff_from_files_roundtrip(self, tmp_path):
        orig_p = tmp_path / "orig.bin"
        patched_p = tmp_path / "patched.bin"
        orig = b"\xde\xad\xbe\xef original"
        patched = b"\xde\xad\xbe\xef patched!"
        orig_p.write_bytes(orig)
        patched_p.write_bytes(patched)
        patcher = Patcher()
        ps = patcher.diff_from_files(str(orig_p), str(patched_p))
        result = patcher.apply(orig, ps.patches)
        assert result == patched
