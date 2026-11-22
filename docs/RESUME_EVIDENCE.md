# 公开证据台账

当前成果为 Phase 0 的业务、架构、验收与开发设计。此阶段可以描述已设计空头欧式看涨期权的自融资账本和独立验证方案。Phase 1 已实现解析定价及敏感度，验证记录见下方。Phase 2 已实现终值模拟及估值，结果见下方。Phase 3 已合并并提供对冲账本，Phase 4 已合并。规划输入不能作为运行结果。

|待验证能力|预期代码与测试定位（拟建）|需附的公开证据|状态|
|---|---|---|---|
|解析定价和敏感度|src/optionlab/pricing.py、greeks.py；tests/test_analytical.py|下方 Phase 1 记录及可重跑示例|已实现，本地验证通过|
|随机估值|src/optionlab/simulation.py；tests/test_monte_carlo.py|[Phase 2 验证记录](MC_VALIDATION_REPORT.md)，含实际路径数、独立样本数、SE 与覆盖率|已实现，本地验证通过|
|自融资复制与基础比较（阶段 3）|portfolio、hedging；同点及跨期权益对账、股息网格收敛|可重放账本、结算差额、日/周 P&L 与误差及成本比较；q=0 主基准，q>0 收敛误差表|已合并|
|高级风险分析（阶段 4）|risk、pnl；手算尾损与归因测试|[VaR/ES、归因与配对区间](RISK_VALIDATION_REPORT.md)|已合并|
|可复现交付|experiments、reporting、CLI 与 CI|运行记录、安装验证、性能基准及 release 链接|待实施|

每条实绩记录填写：能力描述、合并 SHA/PR、模块和测试永久链接、命令、配置与种子、实际规模、硬件与版本、误差/耗时及单位、结果文件、CI 日志、限制和审核日期。简历表述只能从审核后的记录提取，并限定模型、样本和比较基准。当前不能声称实盘执行、银行业绩、性能提升或策略收益。


## Phase 1 实测记录

代码包含冻结的合约/市场类型、每股多头 BSM call/put 及五项解析 Greeks、
显式边界缺失状态、独立积分及中心差分验证器。正式模块由
examples/analytical_pricing.py 调用。工程具备 src 安装布局及 Python 3.11 CI 配置。

Python 3.12.14、NumPy 2.5.5、SciPy 1.18.1、pytest 9.2.0、Ruff 0.17.6 下，
运行 pytest -q 得到 298 passed、0 failed、0 skipped。
ruff check 和 ruff format --check 通过。远端 CI 的结果需在推送后核实。

独立积分测试网格为 K∈{80,100,120}、T∈{.25,1}、σ∈{.15,.30}、
r∈{−.02,.03}、S=100、q=.01，call/put 共 48 个配置。
最大绝对价格误差为 8.526512829121202e−14，发生于 call、
K=80、T=1、σ=.30、r=−.02，单位为每股币种。
Greeks 测试使用相同配置、估值时间 .1 和三档相对步长
1e−3、1e−4、1e−5。跨全部步长的最大绝对误差依次为
Delta 2.720982037018871e−6、Gamma 1.68990233569144e−6、
Vega 7.78769518561262e−6、Theta 1.937792383444048e−6、
Rho 1.2127424753316518e−7。单位采用架构约定，所有样例满足既定混合公差。

以上为有限网格实测结果。测试文件和示例可用于复核，性能、随机估值和对冲研究待后续阶段。
本次实现提交可由 git log --oneline -- src/optionlab 定位；
合并记录见下表。


另以 Python 3.11.18、NumPy 2.4.6、SciPy 1.17.1、pytest 9.2.0、
Ruff 0.17.6 创建独立虚拟环境并执行非 editable 安装。
同一组 298 项测试全部通过，0 failed、0 skipped，Ruff 两项检查和正式示例通过。
此记录验证当前环境的 Python 3.11 安装路径，远端 Actions 状态另行核实。

## Phase 2 实测记录

详见 [Monte Carlo 研究报告](MC_VALIDATION_REPORT.md)及其原始 JSON 汇总。
报告包含实现源提交、环境、种子配置、误差、覆盖、收敛和资源观察。
本阶段公开 API 为 MonteCarloConfig、MonteCarloResult、gbm_terminal 和 mc_price。
远端 PR、CI 及合并状态须按实际 GitHub 结果核实。

## Phase 3 实测记录

[对冲验证报告](HEDGING_VALIDATION_REPORT.md)记录逐笔账本、手算验证、
同路径日周比较、股息收敛、实验配置、源提交和单次资源观察。
实验终端数组由报告所列命令生成，远端 CI 和 PR 状态须单独核实。

## 合并记录与 Phase 4 证据

main 第一父链确认 Phase 1 PR #2（ed7fd76）、Phase 2 PR #3（c987a3e）、Phase 3 PR #4（bee9f8f）均已合并。此前各阶段本地运行记录保留。Phase 4 实现位于 src/optionlab/risk.py 与 pnl.py，测试位于 tests/test_risk.py 与 test_pnl.py，实测结果见[风险验证报告](RISK_VALIDATION_REPORT.md)。

## Verified merge history

|Phase|PR|Source head|Merge commit|
|---|---|---|---|
|0|[#1](https://github.com/xtong629/options-pricing-hedging-simulator/pull/1)|0be7d62ff2a4d8c7f94123216e46bd9d2602ad7f|70bd8f4b2fccb0e62386f550feb0152e0ec216bb|
|1|[#2](https://github.com/xtong629/options-pricing-hedging-simulator/pull/2)|ecc5e3f6effe1bc01a80c9bf67e1853b4606c54a|ed7fd76107193761f1a3577719df31ef513a2002|
|2|[#3](https://github.com/xtong629/options-pricing-hedging-simulator/pull/3)|059d5ad8664e8d8db75790a8ff413a7eb4912c68|c987a3e38995d2c070e5c0604738f08e06a61a7f|
|3|[#4](https://github.com/xtong629/options-pricing-hedging-simulator/pull/4)|dbede63fea565a32f41066f906b734034e3bbddd|bee9f8fb3787f90c57a0860ba5bf76db9d572775|
|4|[#5](https://github.com/xtong629/options-pricing-hedging-simulator/pull/5)|16e786c9a6bd821639ce7b11dc0e4462897abf7c|79a852083faa0912c6a97b3efee61d135aa9b56c|

## English portfolio descriptions

Two bullets

- Built and validated a Python European options pricing toolkit using independent payoff integration, finite differences and paired antithetic Monte Carlo estimates.
- Compared daily and weekly delta hedges on 10,000 shared simulated paths per volatility setting. At matched 20% volatility and 5 bps fees, daily hedging reduced simulated 95% ES by 112.21 currency units per contract at a mean net P&L cost of 12.48.

Three bullets

- Implemented dividend-adjusted BSM prices and five analytical Greeks with independent quadrature and three finite-difference bump scales.
- Evaluated antithetic sampling at equal path budgets over 100 repetitions. At 100,000 paths, the one-year ATM call empirical MSE was 51% of standard MC under the documented parameters.
- Built a self-financing short-call ledger and reconciled financing, dividends, trade fees and expiry settlement. Quantified paired strategy differences and compared local Greek approximations with full revaluation.

Evidence and reproduction commands appear in the [MC](MC_VALIDATION_REPORT.md), [hedging](HEDGING_VALIDATION_REPORT.md), [risk](RISK_VALIDATION_REPORT.md) and [release audit](RELEASE_AUDIT.md) reports.
