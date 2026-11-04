"""Analyze frozen platform CTA outcomes; this module is not a trading engine."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.vq import kmeans2


def metrics(values: np.ndarray) -> dict:
    x = np.asarray(values, dtype=float)
    if not len(x) or not np.isfinite(x).all() or (x <= -1).any():
        raise ValueError("收益为空、非有限值或不适合净值复利计算")
    nav = np.r_[1.0, np.cumprod(1 + x)]
    vol = x.std(ddof=1) if len(x) > 1 else 0
    return {"days": len(x), "sharpe": float(np.sqrt(252) * x.mean() / vol) if vol > 0 else None,
            "total_return": float(nav[-1] - 1),
            "max_drawdown": float(np.min(nav / np.maximum.accumulate(nav) - 1))}


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(outcomes: pd.DataFrame, features: pd.DataFrame, cfg: dict) -> tuple:
    cols = {"date", "symbol", "parameter", "gross_return", "fee_return", "slippage_return"}
    if not cols <= set(outcomes):
        raise ValueError(f"收益文件缺少 {sorted(cols-set(outcomes))}")
    needed = {"symbol", "feature_start", "feature_end", *cfg["feature_columns"]}
    if not needed <= set(features):
        raise ValueError(f"特征文件缺少 {sorted(needed-set(features))}")
    d, f = outcomes.copy(), features.copy()
    d["date"] = pd.to_datetime(d.date, errors="raise")
    d["parameter"] = d.parameter.astype(str)
    for c in ("feature_start", "feature_end"):
        f[c] = pd.to_datetime(f[c], errors="raise")
    start, end, test_end = map(pd.Timestamp, (cfg["train_start"], cfg["train_end"], cfg["test_end"]))
    if not start < end < test_end:
        raise ValueError("训练与测试时间顺序无效")
    if (f.feature_start < start).any() or (f.feature_end > end).any() or (f.feature_start > f.feature_end).any():
        raise ValueError("聚类特征必须全部来自冻结训练窗口")
    if f.symbol.duplicated().any() or d.duplicated(["date", "symbol", "parameter"]).any():
        raise ValueError("发现重复特征或重复收益记录")
    numeric = ["gross_return", "fee_return", "slippage_return"]
    if not np.isfinite(d[numeric].to_numpy(float)).all() or (d[["fee_return", "slippage_return"]] < 0).any().any():
        raise ValueError("收益和费用必须有限，费用不能为负")
    if not np.isfinite(f[cfg["feature_columns"]].to_numpy(float)).all():
        raise ValueError("聚类特征包含非有限值")
    train_symbols, unseen = set(cfg["train_symbols"]), set(cfg["holdout_symbols"])
    if not train_symbols or not unseen or train_symbols & unseen:
        raise ValueError("训练品种和保留品种必须非空且互斥")
    if not train_symbols | unseen <= set(f.symbol):
        raise ValueError("品种缺少训练窗口特征")
    d = d[d.symbol.isin(train_symbols | unseen) & d.date.between(start, test_end)].copy()
    parameters = set(map(str, cfg["parameters"]))
    if str(cfg["baseline_parameter"]) not in parameters or set(d.parameter) != parameters:
        raise ValueError("参数网格与冻结配置不符")
    if not d.groupby(["symbol", "date"]).parameter.nunique().eq(len(parameters)).all():
        raise ValueError("逐日收益缺少部分参数，不能公平比较")
    # A missing whole symbol/day must not silently change the equal-weight denominator.
    # The export calendar itself still needs independent source-calendar verification.
    pools = ((d[(d.date <= end) & d.symbol.isin(train_symbols)], len(train_symbols)),
             (d[d.date > end], len(train_symbols | unseen)))
    for rows, expected in pools:
        if rows.empty or not rows.groupby("date").symbol.nunique().eq(expected).all():
            raise ValueError("逐日品种覆盖不完整，不能改变等权分母或静默补零")
    d["net_return"] = d.gross_return - d.fee_return - d.slippage_return
    return d, f.set_index("symbol"), train_symbols, unseen, end


def choose(rows: pd.DataFrame, parameters: list[str]) -> str:
    if rows.empty:
        raise ValueError("参数选择没有训练数据")
    scores = rows.groupby(["symbol", "parameter"]).net_return.mean().groupby("parameter").mean()
    return max(parameters, key=lambda p: (float(scores.get(p, -np.inf)), -parameters.index(p)))


def analyze(outcomes: pd.DataFrame, features: pd.DataFrame, cfg: dict) -> dict:
    d, f, known, unseen, cutoff = validate(outcomes, features, cfg)
    params = list(map(str, cfg["parameters"]))
    train = d[d.symbol.isin(known) & (d.date <= cutoff)]
    if set(train.symbol) != known:
        raise ValueError("训练品种没有完整训练数据")
    symbols = sorted(known)
    x = f.loc[symbols, cfg["feature_columns"]].to_numpy(float)
    mean, std = x.mean(0), x.std(0)
    std = np.where(std > 1e-12, std, 1)
    k = int(cfg.get("clusters", 2))
    if not 1 <= k <= len(symbols):
        raise ValueError("聚类数不合法")
    centers, labels = kmeans2((x-mean)/std, k, minit="++", seed=int(cfg.get("seed", 42)))
    if len(set(labels)) != k:
        raise ValueError("训练数据导致空簇，请调整开发集聚类数")
    all_symbols = sorted(known | unseen)
    z = (f.loc[all_symbols, cfg["feature_columns"]].to_numpy(float)-mean)/std
    assignment = np.argmin(((z[:, None]-centers[None, :])**2).sum(2), axis=1)
    groups = dict(zip(all_symbols, map(int, assignment)))
    unified = choose(train, params)
    cluster_params = {i: choose(train[train.symbol.isin([s for s in symbols if groups[s] == i])], params) for i in range(k)}
    individual = {s: choose(train[train.symbol == s], params) for s in symbols}
    maps = {
        "frozen_baseline": {s: str(cfg["baseline_parameter"]) for s in all_symbols},
        "unified": {s: unified for s in all_symbols},
        "cluster_shared": {s: cluster_params[groups[s]] for s in all_symbols},
        "per_symbol": {s: individual.get(s, unified) for s in all_symbols},
    }
    tests = d[d.date > cutoff]
    scope = {"known_future": known, "unseen_future": unseen}
    reports = []
    for label, pool in scope.items():
        part = tests[tests.symbol.isin(pool)]
        if set(part.symbol) != pool:
            raise ValueError(f"{label} 缺少保留品种")
        for scheme, mapping in maps.items():
            selected = part[part.parameter == part.symbol.map(mapping)]
            coverage = selected.groupby("date").symbol.nunique() / len(pool)
            for cost in (1.0, 1.5, 2.0):
                net = selected.assign(net=selected.gross_return-cost*(selected.fee_return+selected.slippage_return))
                daily = net.groupby("date").net.mean()
                reports.append({"scope": label, "scheme": scheme, "cost_multiplier": cost,
                                "coverage_min": float(coverage.min()), **metrics(daily.to_numpy())})
    train_dates = sorted(train.date.unique())
    stability = []
    for block in np.array_split(train_dates, 3):
        subset = train[train.date.isin(block)]
        if not subset.empty:
            stability.append({"start": str(pd.Timestamp(block[0]).date()), "end": str(pd.Timestamp(block[-1]).date()),
                              "unified_parameter": choose(subset, params)})
    return {"status": "local_analysis_only_platform_evidence_required", "parameter_maps": maps,
            "selection_metric": "equal_symbol_mean_net_daily_return",
            "cluster_model": {"mean": mean.tolist(), "std": std.tolist(), "centers": centers.tolist(), "assignments": groups},
            "training_stability": stability, "metrics": reports,
            "unseen_per_symbol_fallback": unified, "config": cfg}


def main() -> None:
    p = argparse.ArgumentParser(description="固定 CTA 机制的参数共享与未见品种验证")
    p.add_argument("--outcomes", required=True); p.add_argument("--features", required=True)
    p.add_argument("--config", required=True); p.add_argument("--output", required=True)
    a = p.parse_args()
    result = analyze(pd.read_csv(a.outcomes), pd.read_csv(a.features), json.loads(Path(a.config).read_text(encoding="utf-8")))
    result["input_hashes"] = {n: sha256(getattr(a, n)) for n in ("outcomes", "features", "config")}
    out = Path(a.output); out.mkdir(parents=True, exist_ok=False)
    (out/"report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(result["metrics"]).to_csv(out/"comparison.csv", index=False)
    print(json.dumps({"output": str(out), "platform_verified": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
