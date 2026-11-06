# CTA 策略参数怎么选

一套期货策略在螺纹钢上选出来的参数，换到别的品种后还好用吗？这个工具用你已有的回测结果比较几种选法。比如把趋势策略的观察天数固定下来，或者让所有品种共用一套参数、让相近品种分组共用、给每个品种单独挑。它把熟悉的品种和没参与选参的品种分开报告，方便看出复杂选法的好处能不能带到新地方。

适合手里已有几组参数回测、正在决定下一步试哪一组的人。入口读的是各组参数的逐日收益，不会用一张行情表替你生成买卖信号。

## 第一次用，先跑一个示例

在 GitHub 点 **Code → Download ZIP**，解压后在能看到 `start.py` 的文件夹里打开 PowerShell。准备好 Python 3.11 或更新版本，然后依次运行下面三行。安装依赖通常需要联网，跑示例不用账号或密钥。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python start.py --demo --output outputs/first-demo
```

用 macOS 或 Linux 时，把 `.venv\Scripts\python` 换成 `.venv/bin/python`。也可以运行 `.venv\Scripts\python start.py` 打开中文菜单，选 `2` 跑示例。重复运行时换一个新的输出目录。

## 有必要给品种分组吗？

1. 打开 `outputs/first-demo/使用结果.md`，找到「未见品种未来段」。这里看的是没参与选参的品种，在选完参数之后那段时间的表现。想知道换品种还能不能用，就从这里看起。
2. 对照同为 `1 倍` 费用的「统一参数」和「分组共享参数」。在演示数据里，两种方案累计收益都是 4.60%，最大回撤都是 -0.16%，也就是从高点最多跌了 0.16%。单看这次结果，没有必要多加一层分组。
3. 换成自己的数据时，先确认两种方案比的是同一段时间，覆盖的品种也相近。再看费用提高到 `1.5 倍` 或 `2 倍` 后，原来的差距还有没有。想用表格软件筛选，打开 `analysis/comparison.csv`。

示例用的是构造的数据，数字只用来练习读报告。研究新方案时，尽量留出没用来挑参数的品种和后续日期，再做最后一轮比较。

## 换成自己的回测

| 文件 | 放什么 |
| --- | --- |
| `outcomes.csv` | 每个品种、每套候选参数每天的回测收益 |
| `features.csv` | 选参数时已经能看到的品种特征，用来做分组 |
| `config.json` | 事先定好的品种、候选参数、日期和费用 |

把三份文件放在同一个目录。用中文菜单选 `3`，也可以直接运行下面这行。准备文件时可以对照演示输出，字段说明见[数据格式](references/data-contract.md)。

```powershell
.venv\Scripts\python start.py --run --input-dir "我的输入" --output "outputs/我的结果"
```

## 文件放在哪

日常从 [`start.py`](start.py) 进。[`examples/`](examples/) 有研究配置和历史对比表。想单独看看手数、保证金和限价怎样影响模拟成交，按[成交约束示例](references/execution-constraints.md)操作，它不会改写原来的回测。

[详细入门](references/getting-started.md) · [历史商品数据怎么回放](references/replay.md) · [EVO 验证记录](references/evo-recovery-20261105.md)
