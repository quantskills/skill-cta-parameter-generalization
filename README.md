# CTA 参数泛化研究

一组 CTA 参数在训练品种上表现不错，换到没参与选参的品种会怎样？这个 Skill 把固定参数、统一选参和分组共享放进同一个回放口径，分开比较熟悉品种与新市场的表现。

## 可以看什么

- 同一套策略下，各种选参方式在训练期和留出区间表现如何。
- 费用上调后，原来的比较结论是否还站得住。
- 单合约回放里，手数、保证金、限价和未成交持仓如何影响结果。可用[独立成交约束示例](references/execution-constraints.md)逐项检查这些假设。

## 快速开始

需要 Python 3.11 或更新版本。先在项目目录跑一份合成示例，无需账户或行情权限。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python start.py --demo --output outputs/first-demo
```

打开 `outputs/first-demo/使用结果.md` 查看中文报告。macOS 和 Linux 请用 `.venv/bin/python` 替换示例中的 Python 路径。

已有逐日参数收益、训练期特征和冻结配置时，可按[三步入门](references/getting-started.md)组织文件，再运行自己的对照研究。

```powershell
.venv\Scripts\python start.py --run --input-dir "我的输入" --output "outputs/我的结果"
```

逐方案结果可在报告和对比表中查看。每次使用新的输出目录。准备真实数据时，参见[数据协议](references/data-contract.md)和[真实数据回放说明](references/replay.md)。

## EVO 验证

已在 EVO 上实际运行商品历史数据回放，并对结果做过独立重算。中文演示、成交约束示例和 74 项软件测试也在 EVO 运行通过。完整对照可查看[冻结研究配置](examples/historical-study-config.json)、[历史比较表](examples/historical-comparison.csv)和[平台验证记录](references/evo-recovery-20261105.md)。

这些材料用于研究选参和回放条件，便于复查方案在新市场和不同费用下的表现。
