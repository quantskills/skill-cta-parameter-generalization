# 从这里开始

本入口在本地运行，不联网、不登录、不自动安装软件，也不下单。正式评分、模型审查和平台复验不是普通使用的前提。

## 1. 检查环境

需要 Python 3.11 或以上。在本仓库目录打开终端，先运行：

```powershell
python start.py --check
```

检查会列出缺失或不同于已验证版本的依赖；不修改现有环境。未就绪时，手动建立独立环境并安装固定依赖（安装通常需要联网）：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python start.py --check
```

macOS / Linux 将下文的 `.venv\Scripts\python` 换成 `.venv/bin/python`。不要替换平台全局依赖；本入口按仓库固定版本检查，平台历史版本的验证结论仍单独保留。

## 2. 跑合成示例

```powershell
.venv\Scripts\python start.py --demo --output "outputs/我的示例 01"
```

打开输出目录里的 `使用结果.md`，先看本次结果和限制，再通过链接打开原始报告。合成数据只检查流程，不证明真实市场或模型效果。

## 3. 用自己的数据

把以下文件放进一个文件夹，字段和内容按[数据协议](data-contract.md)准备；不能只是改文件名。

| 文件 | 内容 |
|---|---|
| `outcomes.csv` | 同一冻结机制的逐日参数收益 |
| `features.csv` | 训练窗口特征 |
| `config.json` | 冻结品种、参数、时间与费用配置 |

```powershell
.venv\Scripts\python start.py --run --input-dir "我的输入" --output "outputs/我的结果 01"
```

新市场逐品种方案使用训练得到的统一参数回退，不是额外独立证据。

如需观察整数手数、保证金、部分成交等限制，可单独运行假设账本示例：`python scripts/execution_constraints.py --input examples/execution-constraints.json --output outputs/constraints-demo`。先读[执行限制说明](execution-constraints.md)；它不改变历史回测，也不证明真实可成交。

程序只知道文件由使用者提供，不会自动认证数据真实、授权充分、历史发布时间正确或可成交。已看过的保留样本不能再次冒充未见数据。每次必须指定新输出目录，已有目录即停止，不覆盖旧结果。缺文件时不会建立输出目录；内容错误时会停止，可能保留部分诊断产物，修正后换新目录重试。

不带参数运行 `python start.py` 可使用中文菜单；输入 0 或结束输入即可退出。路径有空格时请加双引号。错误提示不会转印输入正文或凭据。

需要实际平台取数或复跑时读[平台运行](platform-run.md)；仅在需要正式评分、模型审查或负责人确认时读[可选评估](assessment.md)。

