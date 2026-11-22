# 1.0.0rc1 release audit

The candidate uses Phase 4 merge 79a8520 as its baseline. The package build targets Python 3.11+ and the tested platforms below use Linux. The installable distribution is optionlab-analytics, the import and executable are optionlab. Git metadata is collected only when the package is running from its own source checkout. Installed runs record their distribution and dependency versions.

## Reproduction checks

1. Build from the project root with `python -m build`. The builder creates a source distribution and builds the wheel from that archive.
2. Install the wheel into a fresh virtual environment. Change to a directory outside the repository and execute `optionlab all --mode full --output research`.
3. From the checkout, execute `python examples/verify_reproduction.py /absolute/path/to/research`. Frozen reports under docs/results supply the reference. This command checks call/put integration and finite differences, every numerical field in the MC examples, grid and convergence study, all 24 hedge summaries, every risk scenario, all bootstrap intervals, audit ledger rows, attribution components and shock results. It requires matching keys, lengths and discrete values. Float comparisons allow absolute 1e−9 or relative 1e−10. Analytical validation uses the Phase 0 tolerances.
4. Execute `python examples/research_figures.py /absolute/path/to/research new-figures` with the plots extra installed. The six PNG figures in docs/figures came from this procedure. Full-size path arrays stay in the user's output directory.

The default full wheel run passed all comparisons against the frozen evidence. Example call/put values were 8.8273212254 and 6.8668912053 per share; at 20% path volatility and 5 bps the contract-level daily and weekly ES reproduced 142.23 and 254.44. Environment, elapsed time, Git provenance and peak RSS are run-specific metadata. All historical JSON artifacts are retained at their original paths. The pricing regression suite separately covers the entire Phase 1 integration and finite-difference grids.

## Performance observation

Linux x86_64 AMD EPYC 9V74, Python 3.12.14, NumPy 2.5.5, SciPy 1.18.1. The benchmark launched four separate installed CLI processes per mode with OpenBLAS and OpenMP thread counts set to one. One warm-up was excluded. Elapsed time includes startup, simulation and output serialization. Peak RSS is the largest process high-water mark among the three measured runs (Linux wait4). Size is the sum of output file lengths for the first measured run.

| Mode | Three elapsed times (s) | Median (s) | Peak RSS (MiB) | Output bytes |
|---|---|---:|---:|---:|
| Fast | 0.699, 0.771, 0.768 | 0.768 | 82.82 | 520263 |
| Full | 16.701, 17.126, 16.686 | 16.701 | 98.51 | 6806469 |

These measurements cover the research payload and metadata at benchmark time. Later metadata additions can change serialized byte counts. MC reduces up to 4,096 independent observations at a time. Hedge and risk studies retain terminal statistics and process up to 512 paths per batch. M1 runtime and peak RSS remain unmeasured.

## Review and release gates

The review found hard-coded temporary output paths and repository-dependent Git calls in the hedge/risk example runners. Installed study functions now take their destinations and sampling budgets explicitly. Existing example commands still work. All pricing, cash-flow, risk and attribution calculations continue through the Phase 1–4 numerical modules. Tests include output collision protection and invalid configuration. CI is configured for both Python versions, packaging and an isolated wheel smoke run. Hosted CI, PR approval and a final release decision are separate outstanding gates.

## Local validation outcome

The complete suite passed 374 tests with zero failures and zero skips on Python 3.11.18 (NumPy 2.4.6, SciPy 1.17.1) and Python 3.12.14 (NumPy 2.5.5, SciPy 1.18.1), using non-editable wheel installs outside the checkout. Ruff lint and format checks passed on the source tree. The candidate sdist includes research scripts, frozen JSON evidence, reports and figures. The wheel includes its CLI entry point and all required runtime modules. No runtime resource files are required. The final wheel was reinstalled on both versions and its fast workflow (3.11) and full workflow (3.12) completed. The final full run passed the frozen numerical comparison.

The two added tests verify output preservation on an existing destination and rejection of invalid configuration before output creation. All 372 pre-existing numerical and accounting tests remain present. Version 1.0.0rc1 is a candidate choice for review. Hosted CI and release authorization remain pending.
