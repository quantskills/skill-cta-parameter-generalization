# CTA 参数泛化研究

在熟悉的期货品种上选出来的参数，换到没参与训练的品种后还合适吗？这个 Skill 在相同的策略和费用条件下比较固定参数、统一选参、分组共享和逐品种选参，让你判断更复杂的方案是否值得继续研究。

## 快速上手

在代码目录打开 PowerShell。需要 Python 3.11 或更新版本。首次安装依赖通常需要联网，示例运行不需要账号或密钥。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python start.py --demo --output outputs/first-demo
```

macOS 或 Linux 用 `.venv/bin/python` 替换命令中的 Python 路径。再次运行时换一个新的输出目录。

## 例子 · 统一选参和分组共享怎么比？

打开 `outputs/first-demo/使用结果.md`，找到「未见品种未来段」，把费用倍数相同的两行放在一起看。在合成示例里，原费用下两种方案的累计收益都是 4.60%，最大回撤都是 -0.16%。这两项指标没有给出换成分组共享的理由。用自己的数据时，先看样本覆盖率是否相近，再检查提高费用后判断会不会改变。需要筛选和留档时，用 `analysis/comparison.csv`。

## 换成自己的数据

准备逐日参数收益 `outcomes.csv`、训练期特征 `features.csv` 和固定研究配置 `config.json`。字段与日期边界见[三步入门](references/getting-started.md)。

```powershell
.venv\Scripts\python start.py --run --input-dir "我的输入" --output "outputs/我的结果"
```

想看成交条件的影响，可用[单合约成交约束回放](references/execution-constraints.md)单独检查手数、保证金和限价。它是独立研究示例，不会改写原回测结果。

## 参考资料

[数据协议](references/data-contract.md) · [实际商品数据回放](references/replay.md) · [历史对比表](examples/historical-comparison.csv) · [EVO 验证记录](references/evo-recovery-20261105.md)
