"""Demo analysis-pass plugin: annotates graph block stats. Used to test discovery."""
from dec_engine.dec_impl.plugin.registry import entry_point_pass


@entry_point_pass
class GraphStatsPass:
    """Counts blocks/edges and stores stats on the graph's metadata."""

    name = "graph_stats"

    def analyze(self, graph):
        blocks = list(graph.blocks.keys())
        edges = sum(len(getattr(b, "successors", [])) for b in graph.blocks.values())
        graph.metadata["plugin_stats"] = {
            "blocks": len(blocks),
            "edges": edges,
        }
        return graph
