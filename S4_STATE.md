# viv-decomp — Project State (S1–S8 progress)

Handoff doc for resuming work on the decompiler. Last updated after the S8
plugin system. Phases S1–S7 complete + S6 done; S8 plugin foundation done.

## Active branch & git state
- **Current branch:** `s8-plugin-system` (last work: plugin system)
- Test suite: **438/438 passing**
- PR#13 (open): S8 plugin system

## Branch map / PRs
| Branch | Contents | PR |
|--------|----------|----|
| `phase0-ir-layer` | IR + symbolik layer | #1 merged |
| `phase2-control-flow` | S2 loop reconstruction + S3 graph-aware types | #3 merged |
| `s4-memory-model` | S4 memory: stack-frame + call graph | #4 merged |
| `s5-multi-arch` / `s5-extended-arch` | S5 arch selection + aliases/CLI | #5, #7 merged |
| `s7-quality-gate` / `s7-benchmark` / `s7-loop-harden` | S7 quality + benchmark + robustness | #6, #8, #9 merged |
| `s6-qt-viewer` / `s6-qt-gui` / `s6-qt-integrate` | S6 headless export + Qt viewer + app | #10, #11, #12 merged |
| `s8-plugin-system` | S8 plugin system (passes + formatters) | **#13 open** |

## What's done (S1–S8 foundation)
- **S0/S1** IR layer, builder, formatter, SSA.
- **S2** Structured control flow: `while(cond){body}` reconstruction in `PrettyPrinter`.
  Fixed a real idom bug (min→max) that blocked loop-header detection.
- **S3** `TypeAnalyzer.analyze_graph()` — graph-aware type propagation over the CFG.
- **S4** `StackFrameAnalyzer` + `CallGraphBuilder`.
- **S5** `ArchSelector` (amd64/i386 + arm/mips/ppc aliases + `--arch` CLI).
- **S6** Headless graph export (JSON/SVG/DOT) + PyQt6 graph viewer + interactive
  `DecompilerApp` (`--view` CLI). Headless via `QT_QPA_PLATFORM=offscreen`.
- **S7** Quality metrics + gate + benchmark suite (loop/diamond/call corpus) +
  loop-hang hardening fix.
- **S8** `PluginRegistry` for analysis passes + output formatters, discovery via
  entry_point decorators, wired into `VivisectDecompiler` (passes + formatter).

## Key files
- `dec_engine/dec_impl/output/pretty.py` — structured CFG walker
- `dec_engine/dec_impl/structuring/domtree.py` — dominators + back-edges (hardened)
- `dec_engine/dec_impl/type_inference/analyze.py` — TypeAnalyzer
- `dec_engine/dec_impl/memory/stack.py`, `memory/callgraph.py` — memory model
- `dec_engine/dec_impl/arch/selector.py` — ArchSelector
- `dec_engine/dec_impl/quality/metrics.py`, `quality/benchmark.py` — quality
- `dec_engine/dec_impl/export/graph.py` — JSON/SVG/DOT export
- `dec_engine/dec_impl/plugin/registry.py` — plugin system (S8)
- `viv_decomp/qt_viewer.py`, `viv_decomp/qt_app.py` — Qt viewer/app
- `viv_decomp/decompiler.py` — pipeline orchestration

## Known quirk (IMPORTANT)
Vivisect's ELF `analyzePLT` raises `Invalid File: None` and aborts real-binary graph
extraction (`/bin/ls`, `/usr/bin/yes`). Benign but prevents validating against real
binaries through the current loader. **Workaround:** validate via synthetic graphs
(see tests/benchmarks). Real-binary validation needs a Vivisect version fix or
workspace-level fallback.

## IR MemRef shapes (for the stack analyzer)
1. `MemRef(base=Var('rbp'|'rsp'), offset=Const(signed), size=...)` — Vivisect style
2. `MemRef(base=BinOp(SUB/ADD, Var(base), Const(k)), offset=Const(0), size=...)` — IR style
`_frame_offset()` in `stack.py` converts both to `(base_reg, signed_offset)`.

## Pipeline entry points
- `VivisectDecompiler.decompile_address(funcva, name)` → `DecompOutput` (incl. `quality` verdict)
- `VivisectDecompiler.export_graph(funcva, fmt)` → JSON/SVG/DOT string
- `VivisectDecompiler(..., plugin_registry=reg, passes=[...], formatter=...)`
- `PluginRegistry().discover_from([path])` → merge decorated plugins
- `python -m viv_decomp BIN --view` → interactive Qt app
- `python tests/benchmarks/run_benchmark.py` → CI quality gate

## Remaining phases
- **S8** remaining: binary patching (diff/apply/regression), LLVM backend,
  neural type inference. Plugin system (done) makes these pluggable.

## GitHub workflow convention
Fork → apply to fork branch → PR against upstream `atlas0fd00m/viv-decomp`.
gh CLI unauthenticated: use curl + GITHUB_TOKEN. PR `--head` must be
`<fork-owner>:<branch>`.
