import importlib.util
import json
from pathlib import Path
import pandas as pd
from test_replay_adapter import fixture

def test_full_existing_engine_study_produces_auditable_comparison(tmp_path):
    path=Path(__file__).parents[1]/'scripts/run_study.py'
    assert path.exists(), 'Study runner is not implemented'
    spec=importlib.util.spec_from_file_location('run_study',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    maps,bars=fixture(400); all_maps=[]; all_bars=[]
    for i,s in enumerate('XYZ'):
        m=maps.copy(); b=bars.copy()
        m['underlying_symbol']=s; m['symbol']=s+m.symbol
        b['symbol']=s+b.symbol
        b[['close','day_session_open']]*=1+i*.1
        all_maps.append(m); all_bars.append(b)
    data=tmp_path/'data'; data.mkdir()
    pd.concat(all_maps).to_csv(data/'mapping.csv',index=False,date_format='%Y%m%d')
    pd.concat(all_bars).to_csv(data/'bars-0000.csv',index=False,date_format='%Y%m%d')
    cfg={'train_start':'2019-02-01','train_end':'2019-12-01','test_end':'2020-06-01',
         'train_symbols':['X','Y'],'holdout_symbols':['Z'],'parameters':['10_60','20_60'],
         'baseline_parameter':'20_60','feature_columns':['annual_volatility','autocorrelation_1','trend_ratio_20'],
         'clusters':1,'seed':42,'map_lag_sessions':2,'map_lag_sensitivity':[],
         'fee_bps_one_way':4,'slippage_bps_one_way':4,'fixed_notional_fraction':.25}
    config=tmp_path/'config.json';config.write_text(json.dumps(cfg),encoding='utf-8')
    module.run_study(config,data,tmp_path/'result')
    report=json.loads((tmp_path/'result/report.json').read_text(encoding='utf-8'))
    assert len(report['metrics'])==24
    assert report['status']=='local_analysis_only_platform_evidence_required'
    ledger=pd.read_csv(tmp_path/'result/execution-ledger.csv')
    assert len(ledger)>500
    last=ledger.sort_values('date').groupby(['symbol','parameter']).tail(1)
    assert (last.fee_return >= last.weight.abs()*4/10000-1e-12).all(), 'Test horizon must include terminal liquidation'
    manifest=json.loads((tmp_path/'result/input-manifest.json').read_text(encoding='utf-8'))
    assert manifest['engine_reused_unmodified'] is True
