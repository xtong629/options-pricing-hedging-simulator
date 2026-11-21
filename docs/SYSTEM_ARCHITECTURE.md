# 系统架构与金融口径

## 组件和数据流

采用单进程 Python 3.11+ 与 src 布局。拟建 src/optionlab/{instruments,market,pricing,greeks,simulation,portfolio,hedging,risk,pnl}.py，包内 experiments 负责配置和编排，reporting 负责 Pandas 表和 Matplotlib 图。tests/validation 存独立基准，configs、reports 和 tests 对应输入、研究输出与验证。CLI 仅解析参数并调用 experiments。NumPy 处理向量批次，SciPy 提供正态分布与独立积分工具。业务层不读文件，账本不依赖图表，验证器不向生产定价提供结果。

合约与市场 → 解析价格及 Greeks；合约与 Q 终值样本 → MC 估计。P 路径逐时输入策略 → 目标股数 → 成交与账本 → 终值/持有期归因 → 风险表与报告。路径源、成本函数与策略是可替换接口；组合扩展按合约 ID 汇总风险，股票按标的净额成交。未来市场适配器产生同样的时点快照，曲面或新过程另行实现与验证。

|模型或接口草案|字段、结果或职责|
|---|---|
|EuropeanOption / MarketSnapshot|冻结 dataclass；call/put、K、到期年数、乘数；当前 t、S、r、q、隐含波动率。估值时间剩余 τ=T−t|
|price(option, market) / greeks(option, market)|每股多头价值与具名 Delta/Gamma/Vega/Theta/Rho；合约方向和数量在组合层处理|
|mc_price(option, market, config, rng)|返回现值、SE、区间、路径数、独立样本数；显式 Generator|
|PathSource / HedgeRule|以当前市场状态向前一步；策略仅接收当前快照和持仓，返回目标股数|
|PortfolioState / TradeRecord|时点、带符号合约数、股票股数、现金；成交记录含路径、时点、成交前后股数、股数变化、价格、费用与现金余额|
|CashEntry / simulate_hedge|按事件记录权利金、融资、股息、股票买卖、费用和结算；返回逐路径终值及选定路径审计明细|
|summarize(losses) / attribute(ledger, marks)|尾部指标与分项损益；实验层附配置、种子、版本和路径标识|

## 解析模型

同一币种，连续复利，常数 r、连续股息率 q，可借贷及持有碎股，无抵押品或违约；时间以年计，基准一年 252 等分交易步。要求所有输入有限、S,K>0、τ,σ≥0，允许负利率。令 η 为 call 的 +1 或 put 的 −1，A=S exp(−qτ)，B=K exp(−rτ)，d1=[ln(S/K)+(r−q+σ²/2)τ]/(σ√τ)，d2=d1−σ√τ，N、φ 为标准正态 CDF、PDF。

|每股量|内部单位与公式|
|---|---|
|价值|η[A N(ηd1)−B N(ηd2)]|
|Delta|η exp(−qτ) N(ηd1)|
|Gamma|exp(−qτ) φ(d1)/(Sσ√τ)|
|Vega|A φ(d1)√τ，每单位绝对波动率|
|Theta|−A φ(d1)σ/(2√τ) + η[q A N(ηd1)−r B N(ηd2)]，日历时间每年|
|Rho|ητ B N(ηd2)，每单位利率|

报告 1 vol point、1 bp、每交易日分别乘 0.01、0.0001、1/252。到期付 max(η(S−K),0)，σ=0 时取 max(η(A−B),0)。边界价格始终可用；首版 Greeks API 在 τ=0 或 σ=0 明确返回边界状态和缺失敏感度，策略要求到期前正隐含波动率，到期直接结算。深尾用负参数 CDF 和平价构造实值价格，验证绝对误差。

## 自融资时序

设一份空头合约、乘数 m>0，期初外部资金为零。收到 mC₀，购买 H₀=mΔ₀ 股，以 c=费率bps/10000 扣费。每笔成交 u=目标股数−原股数，现金变化 −uS−c|u|S。无交易时费用为零。权利金、期权负债和股票价值分别入账。任一到期前时点权益为 cash+HS−mC。

区间 (i,j] 保持 H_i。现金先按 exp(rΔt) 增长，区间股息按左端股票价值近似为 H_i q S_i Δt，于右端入账；即使周度调仓也逐基础日计息派息。日末按当时 ex-dividend 价格重估，若到调仓日则成交。到期只卖清股票、支付 m max(S_T−K,0)，余现即终端 P&L。周度每五步、日度每步，尾段不足一周仍结算。基准 q=0；非零 q 另做网格细化。成本按成交额计算，包含首次建仓及清仓。

GBM 精确步进 S'=S exp[(b−q−σ²/2)h+σ√h Z]。Q 定价取 b=r、σ=隐含波动率；P 对冲研究取 b=设定的总回报漂移 μ、σ=设定的路径波动率。单条路径的样本已实现波动率另行估计。模型错设比较固定路径改变定价波动率；离散误差基准先匹配波动率且成本为零。每套策略共享相同基础日路径。
