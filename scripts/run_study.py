"""Run the preregistered sharing experiment over frozen real-contract exports."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from analyze import analyze,metrics
from replay_adapter import prepare_indexes,replay,training_features,ENGINE_SHA256


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_study(config_path,data_dir,output):
    cfg=json.loads(Path(config_path).read_text(encoding='utf-8'))
    if cfg['fixed_notional_fraction']!=.25:
        raise ValueError('This frozen replay uses a 25% notional fraction')
    folder=Path(data_dir);out=Path(output);out.mkdir(parents=True,exist_ok=True)
    if (out/'report.json').exists():raise ValueError('Study results already exist; do not overwrite a holdout evaluation')
    paths=sorted(folder.glob('bars-*.csv'))
    if not paths:raise ValueError('No actual-contract bars found')
    # Identical rows across acquisition chunks may be collapsed, conflicting rows may not.
    bars=pd.concat([pd.read_csv(p,dtype={'date':str}) for p in paths],ignore_index=True)
    bars=bars.drop_duplicates()
    if bars.duplicated(['symbol','date']).any():raise ValueError('Conflicting duplicate contract bars')
    mapping=pd.read_csv(folder/'mapping.csv',dtype={'date':str})
    manifest={'at':datetime.now(timezone.utc).isoformat(),'config_sha256':digest(config_path),
              'mapping_sha256':digest(folder/'mapping.csv'),'bar_files':{p.name:digest(p) for p in paths},
              'engine_sha256':ENGINE_SHA256,'engine_reused_unmodified':True,
              'python':sys.version,'data_rows':len(bars),'map_rows':len(mapping),
              'execution':'historical same-contract day-open economic replay; not simulated fills',
              'mapping_publication_verified':False}
    (out/'input-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    outcomes=[];feature_rows=[];ledgers=[];all_indexes={}
    for symbol in cfg['train_symbols']+cfg['holdout_symbols']:
        m=mapping[mapping.underlying_symbol.eq(symbol)]
        m=m[pd.to_datetime(m.date.astype(str),format='%Y%m%d')<=pd.Timestamp(cfg['test_end'])]
        b=bars[bars.symbol.isin(m.symbol.unique())]
        indexes=prepare_indexes(m,b,cfg['map_lag_sessions'])
        all_indexes[symbol]=(m,b)
        indexes.to_csv(out/(symbol+'-causal-indexes.csv'),index=False)
        feature_rows.append(training_features(indexes,symbol,cfg['train_start'],cfg['train_end']))
        for parameter in cfg['parameters']:
            fast,slow=map(int,parameter.split('_'))
            run=replay(indexes,fast,slow,out/'replay'/symbol/parameter,
                       cfg['fee_bps_one_way'],cfg['slippage_bps_one_way'])
            run['symbol']=symbol;run['parameter']=parameter
            run=run[run.date.between(pd.Timestamp(cfg['train_start']),pd.Timestamp(cfg['test_end']))]
            outcomes.append(run[['date','symbol','parameter','gross_return','fee_return','slippage_return']])
            ledgers.append(run)
    d=pd.concat(outcomes,ignore_index=True);f=pd.DataFrame(feature_rows)
    d.to_csv(out/'outcomes.csv',index=False);f.to_csv(out/'features.csv',index=False)
    pd.concat(ledgers,ignore_index=True).to_csv(out/'execution-ledger.csv',index=False)
    result=analyze(d,f,cfg)
    # Same calendar is required here; a changing denominator cannot improve returns.
    for pool in (cfg['train_symbols'],cfg['holdout_symbols']):
        counts=d[d.symbol.isin(pool)].groupby('date').symbol.nunique()
        if not counts.eq(len(pool)).all():raise ValueError('Unequal daily symbol coverage')
    result['input_hashes']={name:digest(out/(name+'.csv')) for name in ('outcomes','features')}
    result['input_hashes']['config']=digest(config_path)
    yearly=[];d['date']=pd.to_datetime(d.date);test=d[d.date>pd.Timestamp(cfg['train_end'])]
    selected_daily={}
    for scope,pool in [('known_future',cfg['train_symbols']),('unseen_future',cfg['holdout_symbols'])]:
        part=test[test.symbol.isin(pool)].copy()
        for scheme,assignment in result['parameter_maps'].items():
            sel=part[part.parameter.eq(part.symbol.map(assignment))].copy()
            sel['net']=sel.gross_return-sel.fee_return-sel.slippage_return
            daily=sel.groupby('date').net.mean()
            selected_daily[(scope,scheme)]=daily
            for year,segment in daily.groupby(daily.index.year):
                yearly.append({'scope':scope,'scheme':scheme,'year':int(year),**metrics(segment.to_numpy())})
    pd.DataFrame(yearly).to_csv(out/'yearly.csv',index=False)
    deltas=[]
    for (scope,scheme),daily in selected_daily.items():
        base=selected_daily[(scope,'frozen_baseline')]
        if not daily.index.equals(base.index):raise ValueError('Comparison calendar mismatch')
        diff=(daily-base).to_numpy(); rng=np.random.default_rng(42)
        means=[];block=20;n=len(diff)
        for _ in range(1000):
            starts=rng.integers(0,n,size=int(np.ceil(n/block)))
            sampled=np.concatenate([diff[(s+np.arange(block))%n] for s in starts])[:n]
            means.append(float(sampled.mean()*252))
        deltas.append({'scope':scope,'scheme':scheme,'annualized_mean_net_delta':float(diff.mean()*252),
                       'descriptive_block_bootstrap_95_interval':np.quantile(means,[.025,.975]).tolist(),
                       'block_sessions':block,'bootstrap_repeats':1000,
                       'note':'paired descriptive interval; multiple schemes and historical selection limit inference'})
    result['baseline_differences']=deltas
    lag_results=[]
    for lag in cfg.get('map_lag_sensitivity',[]):
        lag_rows=[]
        for symbol,(m,b) in all_indexes.items():
            indexes=prepare_indexes(m,b,lag)
            for parameter in sorted(set(assignment[symbol] for assignment in result['parameter_maps'].values())):
                fast,slow=map(int,parameter.split('_'))
                r=replay(indexes,fast,slow,out/'lag-stress'/str(lag)/symbol/parameter,
                         cfg['fee_bps_one_way'],cfg['slippage_bps_one_way'])
                r=r[r.date.between(pd.Timestamp(cfg['train_end'])+pd.Timedelta(days=1),pd.Timestamp(cfg['test_end']))].copy()
                r['symbol']=symbol;r['parameter']=parameter;lag_rows.append(r)
        all_lag=pd.concat(lag_rows,ignore_index=True)
        for scope,pool in [('known_future',cfg['train_symbols']),('unseen_future',cfg['holdout_symbols'])]:
            for scheme,assignment in result['parameter_maps'].items():
                sel=all_lag[all_lag.symbol.isin(pool)&all_lag.parameter.eq(all_lag.symbol.map(assignment))]
                daily=(sel.assign(net=sel.gross_return-sel.fee_return-sel.slippage_return).groupby('date').net.mean())
                lag_results.append({'map_lag_sessions':lag,'scope':scope,'scheme':scheme,
                                    'parameters_refit':False,**metrics(daily.to_numpy())})
    result['mapping_lag_stress']=lag_results
    result['limitations']=['Historical dominant publication time unverified',
        'Daily-open replay does not model limit queues, partial fills, margin or integer lots',
        'One fixed historical universe and one mechanism; no live profitability claim',
        'No test-period retuning; per-symbol parameters for unseen symbols fall back to training unified']
    (out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(result['metrics']).to_csv(out/'comparison.csv',index=False)
    print(json.dumps({'output':str(out),'status':result['status'],'outcome_rows':len(d),
                      'features':len(f),'comparison_rows':len(result['metrics']),'engine_sha256':ENGINE_SHA256}),flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--data',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run_study(a.config,a.data,a.output)
