# 输入协议

`outcomes.csv` 每行对应一个品种、参数与交易日。

| 字段 | 含义 |
|---|---|
| date | 收益归属交易日 |
| symbol | 品种或可核验的连续合约标识 |
| parameter | 冻结参数标识，文本 |
| gross_return | 同一固定 CTA 机制的未扣费简单收益 |
| fee_return | 手续费折算收益，非负；另注明实际费率或模型假设 |
| slippage_return | 滑点折算收益，非负；另注明实际成交估计或模型假设 |

每个品种每一天必须包含全部候选参数。缺失不能填零。每日收益必须已按同一个仓位和风险规则计算，不能在不同参数间偷偷改变风险预算。

训练品种在训练段、全部品种在保留段必须具有相同的输入交易日覆盖，否则程序停止，不能让缺行情改变等权分母。整组品种同时漏掉的交易日仍须与独立源日历核对，程序不能从缺失文件中还原它。

组合口径为 `R_t = (1/N) × Σ_s [gross_return_s,t − 成本倍数 × (fee_return_s,t + slippage_return_s,t)]`。N 是该评价范围的冻结品种数，不随当天有数据的品种数变化。本次每个品种子账户的方向敞口为 ±25%，再对这些子账户等权平均；并不是每品种各占整个账户 25%，也不是把全部品种损益直接相加。累计收益按 `Π_t(1+R_t)−1` 计算，不可与不同敞口口径的账户收益直接比较。

`features.csv` 包含 `symbol,feature_start,feature_end` 和配置指定的特征列。可用训练期波动率、趋势持续性和成交活跃度；数据来源、公式及单位另外记录。所有特征窗口必须落在冻结训练段内。

`config.json` 包含 `train_start,train_end,test_end,train_symbols,holdout_symbols,parameters,baseline_parameter,feature_columns,clusters,seed`。

开发期的一个例子如下。实际品种、时期和参数标识须以 EVO 已存在的 CTA 机制为准。

```json
{"train_start":"2020-01-01","train_end":"2023-12-31","test_end":"2025-12-31","train_symbols":["A","B","C","D"],"holdout_symbols":["E"],"parameters":["p10","p20","p40"],"baseline_parameter":"p20","feature_columns":["volatility","trend_persistence"],"clusters":2,"seed":42}
```

输出 `comparison.csv` 与 `report.json`，含参数选择、冻结聚类中心、训练分块重选结果、1/1.5/2 倍费用压力和保留段覆盖率。三个训练分块只是稳定性检查，不能用于重新选择测试段结论。

训练选参目标为先求每个品种的日均扣费收益，再在品种间等权平均。这样上市较早、历史较长的品种不会仅因行数更多就主导共享参数。该目标随基线一起冻结，不看保留段后改成另一项指标。
