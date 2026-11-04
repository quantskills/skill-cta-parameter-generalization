# EVO 真实数据回放

此路径用官网 EVO 的项目文件与 Python 运行入口，不需要在本机连接模型或保存 PandaData 密码。先在 EVO 项目中通过平台的数据连接功能完成授权。

## 固定机制

third_party/global_macro_trend/backtest.py 是社区既有双均线机制的原文件；来源、提交、许可和散列见该目录 NOTICE.md。replay_adapter.py 启动时校验散列，直接调用原信号、仓位与 run()，不复制出另一个趋势引擎。固定名义仓位为 25%，不同时优化风险预算。

原引擎按每日价格变动计收益。本适配层为它提供按实际合约逐段构建的日间开盘收益指数，并额外滞后信号；收益归属日的仓位只依赖前两日或更早的收盘信息。原引擎元信息中的成交标签和其 CAGR/波动率式 Sharpe 不用于本研究最终报告。

## 复跑

将本 Skill 目录上传到同一个 EVO 项目；在官网项目终端或 Python 脚本入口依次执行。以下命令假设当前目录为 Skill 根目录，config.json 使用随研究冻结的实际配置，而非边看测试结果边改。

```text
python scripts/collect_pandadata.py --config config.json --output data --phase maps
python scripts/collect_pandadata.py --config config.json --output data --phase bars --offset 0 --limit 8
```

maps 阶段会给出总批次数。在每批成功后把 offset 增加 8，直到覆盖全部批次。每次最多取 8 批；已存在且散列一致的批次会复用。配置漂移、空数据、无索引旧文件或散列不一致会停止，不自动重新登录、不更换供应商。

```text
python scripts/run_study.py --config config.json --data data --output result
```

生成 outcomes.csv、features.csv、execution-ledger.csv、comparison.csv、yearly.csv、report.json 和输入散列。result 中已有 report.json 时禁止覆盖；复现请使用新的输出目录。原始数据的再分发取决于数据授权，公开仓库不要打包账户数据、操作审计或登录信息。

## 口径与失败边界

- 同一持仓区间的两端必须来自同一个实际合约，不能把主连换月跳空计作利润。
- 费用假设和移仓双腿显式计入；末日平仓亦收费。没有券商账单时应称为费用模型，不能称实际手续费。
- 映射滞后不是历史发布时间证明。缺少供应商发布存档时保留限制，并测试更长滞后；敏感性阶段使用主研究冻结的参数，不重新选择测试赢家。
- 缺合约端点、非正价格或冲突记录会停止，不能以填零或删除不利日期修饰覆盖率。
- 这是实际数据上的经济收益回放，不含涨跌停排队、部分成交、保证金、整数手数，也不等同于模拟赛成交。未完成模拟成交核验时，不应称为可直接实盘使用。

运行时保存 EVO 项目编号、每次任务编号和控制参数、控制台原文以及 source/data 散列。报告中的 local_analysis_only_platform_evidence_required 是分析器的证据边界，不能手改为 true；用独立的平台运行回执核实。
