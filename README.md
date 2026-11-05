# CTA 参数共享与新市场泛化

本轮增加[独立成交约束回放](references/execution-constraints.md)，用于检查手数、保证金、限价和未成交持仓；不改变原历史回测。最新检查和平台验证边界见[2026-11-05验收记录](references/validation-20261105.md)。

首次使用先看[三步入门](references/getting-started.md)：运行 `python start.py --check` 检查环境，`python start.py` 打开中文菜单。准备好依赖后，运行 `python start.py --demo --output outputs/first-demo`，打开结果目录里的 `使用结果.md`。每次使用新目录；示例是合成数据，不证明真实效果。

自己的数据统一放进一个文件夹，再运行 `python start.py --run --input-dir "我的输入" --output "outputs/我的结果"`。所需文件与准备步骤见入门说明。以下保留原始命令和历史研究记录，供进一步使用；[正式评分与模型审查](references/assessment.md)均为可选，不阻止普通使用。

固定一套已经存在的 CTA 机制，检查同一组参数能否跨品种使用，以及训练期分组共享参数是否比逐品种选参更稳健。

当前为研究版本。已完成一次官网 EVO 实际商品数据回放并通过独立重算，结果不支持本次分组共享方案改善新市场泛化。历史发布时间和模拟成交核验仍未完成，不能直接用于实盘。

## 先跑一个例子

需要 Python 3.11 或以上。下载仓库后，在仓库目录打开终端，先建立独立环境，再安装依赖。首次体验不需要账号或行情权限。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts/demo.py --output outputs/demo-01
```

macOS / Linux 将 `.venv\Scripts\python` 换成 `.venv/bin/python`。演示会生成合成输入和 `outputs/demo-01/analysis/report.json`、`comparison.csv`，仅用于确认安装与分析流程，不是市场效果证明。输出目录必须是新目录；再次运行请换成 `demo-02`，程序不会覆盖旧报告。

## 用自己的数据

按[数据协议](references/data-contract.md)准备 EVO 导出的逐日参数收益、训练期特征和冻结配置。在同一个独立环境中运行以下命令。

```powershell
.venv\Scripts\python scripts/analyze.py --outcomes outcomes.csv --features features.csv --config config.json --output outputs/study
.venv\Scripts\python -m pytest tests -q
```

分析结果保存在 `report.json` 和 `comparison.csv`。其中未见品种的逐品种方案采用训练得到的统一参数回退，报告会明确记录这个选择。

因此，在未见品种范围内，`per_symbol` 与 `unified` 结果相同，不是两份独立的有效性证据。训练目标完全并列时，按冻结配置 `parameters` 中的先后顺序取较早者，不按参数名称排序。

## 实际验证结果

2026 年 11 月完成官网 EVO 实际商品数据回放和独立重算。本次未见品种未来段共 1212 个收益观测日，按原费用模型得到以下累计收益。

| 方案 | 原费用 | 费用增加到两倍 |
|---|---:|---:|
| 固定参数基线 | −4.51% | −6.18% |
| 统一参数 | −5.77% | −7.61% |
| 分组共享参数 | −9.39% | −11.10% |

这次结果不支持采用分组共享方案。工具的用途是把这种比较做清楚，避免仅凭训练期表现选择更复杂的方案，不承诺提升收益。原实验的[冻结配置](examples/historical-study-config.json)和[完整对比表](examples/historical-comparison.csv)随仓库提供。训练期为 2016 至 2020 年，未来段为 2021 至 2025 年，具体品种、参数和费用均以配置文件为准。

代码经过 Kimi-K3 两轮文件审查。修订后的 23 项测试在 Windows Python 3.12、EVO Python 3.11 / Linux 和解压后的交付目录分别通过，零失败、零跳过。测试包含输出防覆盖、合约收益衔接、费用、参数选择及离线演示。修订后重算没有改变历史参数选择和结论，数值最大差约 `7.80e-15`。

`requirements.txt` 固定的独立安装依赖为 NumPy 2.2.6、pandas 2.3.1、SciPy 1.16.1、pytest 9.0.2、PyYAML 6.0.3。EVO 已有环境分别为 1.26.4、2.3.3、1.17.1、9.1.1、6.0.3。两组分别验证，不需要替换平台全局依赖。

后续补强修复了缺失特征日期可能漏过训练边界检查的问题，聚类数量也改为严格整数，不再自动取整。另补非有限输入和打乱输入顺序的检查。本地完整测试现为32项，解压后再次测试及离线演示均通过。原始冻结数据重算后，参数选择与144个对比数值完全相同，没有重新挑选保留期参数。最新平台状态见[本轮复验](references/revalidation-r2.md)。

## 使用限制

回放尚未覆盖涨跌停排队、部分成交、保证金和整数手数。仓库不含原始授权行情或私人平台会话，历史市场实验需要另行取得数据并保留原冻结配置。模型审查和测试通过不等于负责人正式验收。

采集器遇到恰好 10000、50000 或 100000 行的疑似截断批次会停止，需核实服务上限并另建较小的采集计划。这个检查不是完整性证明，仍要核对交易日历、合约和原始来源；不能因“未触发阈值”就认定行情齐全。

只有导出的逐日收益时，按上面的命令分析。需要从实际商品合约取数并复跑固定社区机制时，见[真实数据回放](references/replay.md)；平台证据要求见[运行说明](references/platform-run.md)。本工具不另建趋势环境，所有方案必须由同一个冻结机制产生，不能为了结果更好而混用策略或风险规则。
