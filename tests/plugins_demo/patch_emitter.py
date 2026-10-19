"""Demo plugin: emits byte patches from graph-metadata byte diffs.

Reads ``graph.metadata["original_bytes"]`` / ``["patched_bytes"]`` (bytes) and
stores a computed PatchSet on ``graph.metadata["patch_set"]``. This lets a
caller seed before/after bytes and discover the plugin via the plugin system.
"""
from dec_engine.dec_impl.plugin.registry import entry_point_pass
from dec_engine.dec_impl.patch import PatchSet, compute_diff


@entry_point_pass
class PatchEmitterPass:
    """Annotates graph metadata with a PatchSet derived from byte diffs."""

    name = "patch_emitter"

    def analyze(self, graph):
        original = graph.metadata.get("original_bytes") or b""
        patched = graph.metadata.get("patched_bytes") or b""
        ps = PatchSet(source_desc="plugin patch_emitter")
        if original and patched:
            ps.add_many(compute_diff(original, patched))
        graph.metadata["patch_set"] = ps
        return graph
