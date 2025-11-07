# Benchmark Catalogue

The table below summarises the benchmark models that are pre-packaged with DTPAYNT and are referenced by the experiment runner (`experiments-dts.py`). Each entry includes the relative path inside the repository, the model family, and a short reminder of what behaviour it exercises. All paths are relative to the chosen source tree (`synthesis-original/` or `synthesis-modified/`).

| Benchmark ID | Relative Path | Model Type | Description | Notes |
|--------------|---------------|------------|-------------|-------|
| `csma-3-4` | `models/dts-q4/csma-3-4` | DTS / MDP | Carrier-sense multiple access network with three senders and four exponential back-off levels. Optimises the probability of a successful handshake before a timeout. | Default preset. Large branching factor; good for stressing lower-bound tightening. |
| `consensus-4-2` | `models/dts-q4/consensus-4-2` | DTS / MDP | Parametric consensus protocol with four processes and two initial votes. The objective maximises the probability of reaching agreement without divergence. | Default preset. Balanced workload that exposes steady best-value improvements. |
| `obstacles` | `models/mdp/obstacles` | MDP | Grid-navigation model where an agent must reach a goal region while avoiding obstacles. Optimises reachability under action nondeterminism. | Default preset. Small tree; useful sanity check for logging and plotting pipelines. |
| `csma-3-4-depth3` | `models/dts-q4/csma-3-4` | DTS / MDP | Same model as `csma-3-4`, but the preset enforces a maximum decision-tree depth of three to amplify the frontier size. | Optional preset activated with `--benchmark csma-3-4-depth3`. |
| `grid-easy` | `models/dtmc/grid/grid` | DTMC lifted to MDP family | Classic PRISM grid world with reachability objective (`easy.props`). Highlights breadth-first improvements in shallow trees. | Invoke with `--benchmark models/dtmc/grid/grid`. |
| `maze-concise` | `models/dtmc/maze/concise` | DTMC lifted to MDP family | Maze navigation problem minimising expected steps to the exit. Encourages heuristics that favour high-valued parents. | Invoke with `--benchmark models/dtmc/maze/concise`. |
| `dice-5` | `models/dtmc/dice/5` | DTMC lifted to MDP family | Probabilistic dice model with five dice and hole-encoded strategies. Very small instance that is ideal for smoke tests and unit checks. | Used by `tests/test_simple_priority_search.py`. |

## Discovering More Benchmarks

Run the preset lister inside either source tree to see all registered shortcuts:

```bash
python experiments-dts.py --list
```

Any directory that contains a PRISM (or template) model together with a `.props` file can be passed directly via `--benchmark <relative-path>`. The runner will infer the sketch and property filenames automatically.

When introducing a new reusable preset, update the `DEFAULT_BENCHMARKS` mapping in `experiments-dts.py` so both Docker images share the same shorthand.
