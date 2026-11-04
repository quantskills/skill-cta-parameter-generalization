---
name: cta-parameter-generalization
description: Evaluate parameter sharing for a frozen CTA mechanism on EVO using training-only commodity groups, unseen-symbol and future-period tests, fees, simple baselines and parameter stability. Use exported per-parameter platform outcomes; do not build a new trend trading engine.
metadata:
  platform: EVO
  development_status: platform-replay-verified-execution-pending
  organization: https://github.com/quantskills
---

# CTA 参数共享与新市场泛化

在 EVO 复用已经存在的同一个 CTA 机制，冻结策略版本、参数网格、数据版本与成本口径，再比较固定参数基线、统一参数、训练品种聚类共享参数和逐品种参数。可使用本目录附带的固定社区双均线机制，不能把它冒称为 EVO 原生期货成交引擎。

## 流程

1. 从 EVO 正式入口执行研究并保存会话、运行编号、原始输入输出和环境记录。只下载结果不能证明策略版本相同，需一并保存策略和参数导出。
2. 按 [输入协议](references/data-contract.md) 导出逐日参数收益与训练窗口特征。
   使用附带既有机制时，先读 [真实数据回放](references/replay.md)，按分批采集、固定执行时点和换月双腿费用生成导出。
3. 运行前冻结训练品种、未参与分组品种及时间保留段，参数网格不能看测试结果后修改。
4. 仅在训练品种上拟合标准化与聚类中心。新市场用训练窗口特征分配到冻结中心。
5. 运行 `scripts/analyze.py`。分别报告已见品种未来段和未见品种未来段，保留覆盖率和扣费结果。
6. 对照原始逐笔成交确认费用与合约移仓收益。不能把未经拼接校验的主连价格跳空当利润。
7. 汇报改变的参数选择、结果差异和适用范围。无优势或不稳定时保留负结论。

## 命令

```powershell
python scripts/analyze.py --outcomes outcomes.csv --features features.csv --config config.json --output outputs/study
```

首次使用可运行 `python scripts/demo.py --output outputs/demo-01`，只生成合成数据，不访问账户。所有分析输出使用新目录，保留旧证据。

平台复跑和最终证据要求见 [平台运行](references/platform-run.md)。已有一次官网实际数据回放、独立重算和补强代码的平台复验证据；结论为本次分组泛化无优势。历史发布时间、模拟成交与负责人最终确认仍未完成，不能标注为可直接实盘使用或全部验收通过。
