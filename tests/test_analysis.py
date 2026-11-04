import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analyze import analyze, choose, metrics


def fixture():
    dates = pd.bdate_range("2024-01-01", periods=50)
    rows = []
    for j, symbol in enumerate("ABCDE"):
        for i, date in enumerate(dates):
            for p in ("10", "20", "40"):
                rows.append({"date": date, "symbol": symbol, "parameter": p,
                             "gross_return": .001*(1+int(p)/40)+np.sin(i+j)*.003,
                             "fee_return": .0001, "slippage_return": .0001})
    features = pd.DataFrame({"symbol": list("ABCDE"), "feature_start": "2024-01-01",
                             "feature_end": "2024-02-01", "vol": [1,1.1,4,4.1,2]})
    cfg = {"train_start":"2024-01-01", "train_end":"2024-02-02", "test_end":"2024-03-15",
           "train_symbols":list("ABCD"), "holdout_symbols":["E"], "parameters":["10","20","40"],
           "baseline_parameter":"20", "feature_columns":["vol"], "clusters":2, "seed":42}
    return pd.DataFrame(rows), features, cfg


def test_holdout_results_cannot_change_parameter_selection():
    data, f, cfg = fixture(); before = analyze(data, f, cfg)
    data.loc[(data.date > "2024-02-02") | (data.symbol == "E"), "gross_return"] = .2
    after = analyze(data, f, cfg)
    assert before["parameter_maps"] == after["parameter_maps"]
    assert before["cluster_model"] == after["cluster_model"]


def test_unseen_features_not_used_to_fit_centers():
    data, f, cfg = fixture(); a = analyze(data, f, cfg)
    f.loc[f.symbol == "E", "vol"] = 100000
    b = analyze(data, f, cfg)
    assert a["cluster_model"]["centers"] == b["cluster_model"]["centers"]


def test_future_features_and_partial_grid_rejected():
    data, f, cfg = fixture(); f.loc[0,"feature_end"] = "2024-02-05"
    with pytest.raises(ValueError, match="训练窗口"):
        analyze(data, f, cfg)
    _, f, _ = fixture()
    with pytest.raises(ValueError, match="缺少部分参数"):
        analyze(data.iloc[1:], f, cfg)


def test_cost_stress_and_first_day_drawdown():
    data, f, cfg = fixture(); report = analyze(data, f, cfg)
    matched = [r for r in report["metrics"] if r["scope"] == "unseen_future" and r["scheme"] == "unified"]
    assert matched[0]["total_return"] > matched[-1]["total_return"]
    assert metrics(np.array([-.1]))["max_drawdown"] == pytest.approx(-.1)


def test_overlapping_symbols_rejected():
    data, f, cfg = fixture(); cfg["holdout_symbols"] = ["A"]
    with pytest.raises(ValueError, match="互斥"):
        analyze(data, f, cfg)


@pytest.mark.parametrize("missing_date", ["2024-01-10", "2024-02-15"])
def test_incomplete_symbol_day_cannot_change_equal_weight_denominator(missing_date):
    data, f, cfg = fixture()
    data = data[~((data.symbol == "A") & (data.date == missing_date))]
    with pytest.raises(ValueError, match="品种覆盖"):
        analyze(data, f, cfg)


def test_actual_cli_writes_report_and_hashes(tmp_path):
    data,f,cfg=fixture()
    data.to_csv(tmp_path/"outcomes.csv",index=False); f.to_csv(tmp_path/"features.csv",index=False)
    (tmp_path/"config.json").write_text(json.dumps(cfg))
    script=Path(__file__).parents[1]/"scripts"/"analyze.py"
    args=[sys.executable,"-X","utf8",str(script)]
    for field in ("outcomes","features","config"):
        args.extend(["--"+field,str(tmp_path/(field+(".json" if field=="config" else ".csv")))])
    args.extend(["--output",str(tmp_path/"result")])
    proc=subprocess.run(args,capture_output=True,text=True,encoding="utf-8")
    assert proc.returncode==0, proc.stderr
    report=json.loads((tmp_path/"result"/"report.json").read_text(encoding="utf-8"))
    assert len(report["input_hashes"])==3 and len(report["metrics"])==24
    before = (tmp_path/"result"/"report.json").read_bytes()
    again = subprocess.run(args,capture_output=True,text=True,encoding="utf-8")
    assert again.returncode != 0, "Repeated runs must not overwrite prior evidence"
    assert (tmp_path/"result"/"report.json").read_bytes() == before


def test_training_objective_does_not_overweight_long_history():
    rows=[{"symbol":"A","parameter":"10","net_return":.001} for _ in range(100)]
    rows += [{"symbol":"A","parameter":"20","net_return":0} for _ in range(100)]
    rows += [{"symbol":"B","parameter":"10","net_return":0},{"symbol":"B","parameter":"20","net_return":.1}]
    assert choose(pd.DataFrame(rows),["10","20"])=="20"


def test_parameter_ties_follow_frozen_order_not_lexical_order():
    rows = pd.DataFrame([{'symbol':'A', 'parameter':p, 'net_return':.01} for p in ('z','a')])
    assert choose(rows, ['a','z']) == 'a'
    assert choose(rows, ['z','a']) == 'z'


@pytest.mark.parametrize("column", ["feature_start", "feature_end"])
def test_missing_feature_date_cannot_bypass_training_boundary(column):
    data, features, cfg = fixture()
    features.loc[0, column] = None
    with pytest.raises(ValueError, match="日期"):
        analyze(data, features, cfg)


@pytest.mark.parametrize("clusters", [True, 1.5, "2"])
def test_cluster_count_must_be_explicit_integer(clusters):
    data, features, cfg = fixture()
    cfg["clusters"] = clusters
    with pytest.raises(ValueError, match="聚类数"):
        analyze(data, features, cfg)


@pytest.mark.parametrize("column", ["gross_return", "fee_return", "slippage_return"])
def test_nonfinite_market_inputs_are_rejected(column):
    data, features, cfg = fixture()
    data.loc[0, column] = np.inf
    with pytest.raises(ValueError, match="有限"):
        analyze(data, features, cfg)


def test_input_row_order_does_not_change_frozen_decisions():
    data, features, cfg = fixture()
    before = analyze(data, features, cfg)
    after = analyze(data.sample(frac=1, random_state=17), features.sample(frac=1, random_state=29), cfg)
    assert before["parameter_maps"] == after["parameter_maps"]
    assert before["cluster_model"] == after["cluster_model"]
    for first, second in zip(before["metrics"], after["metrics"]):
        assert first == pytest.approx(second)
