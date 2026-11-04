# 原文件来源

backtest.py 原样来自 https://github.com/quantskills/skill-global-macro-trend-strategy ，提交 2eb638f8da966e51e5d0c026a7bc66a6f408d0c7，路径 scripts/backtest.py，许可 GPL-3.0-only。相应许可全文见 LICENSE。文件 SHA256：dd5fbaf234c57a08910ffecad80e19c001805328d78fde2b5274741a17946bf5。

此目录代码未修改。外部 replay_adapter.py 负责真实合约收益链、执行滞后与换月费用。原引擎输出中 “t+1 close” 是上游元信息，不是本研究实际执行口径；本研究采用声明的日间开盘区间，不使用该标签或上游 Sharpe 公式作为最终指标。
