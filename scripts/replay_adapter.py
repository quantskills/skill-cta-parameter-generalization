"""GPL-3.0-only. Data/timing/cost adapter for an unmodified frozen community engine.

Research replay, not an order/fill simulator. No network or credentials here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ENGINE_SHA256 = 'dd5fbaf234c57a08910ffecad80e19c001805328d78fde2b5274741a17946bf5'


def load_frozen_engine():
    path = Path(__file__).parents[1]/'third_party/global_macro_trend/backtest.py'
    if hashlib.sha256(path.read_bytes()).hexdigest() != ENGINE_SHA256:
        raise ValueError('Frozen engine hash mismatch')
    spec = importlib.util.spec_from_file_location('frozen_global_macro_trend', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def daily_dates(values):
    s = pd.Series(values).copy()
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.to_datetime(s)
    text = s.astype(str)
    return pd.to_datetime(text, format='%Y%m%d' if text.str.fullmatch(r'\d{8}').all() else None, errors='raise')


def prepare_indexes(mapping, bars, map_lag=2):
    """Return same-contract causal signal and day-open return chains.

    Row t earns from day_open(t-1) to day_open(t), held contract selected from
    mapping(t-1-map_lag). Signals at close(t-2) set the exposure for this interval.
    The extra mapping lag does not prove a vendor's historical release timestamp.
    """
    if not isinstance(map_lag,int) or isinstance(map_lag,bool) or map_lag < 1:
        raise ValueError('map_lag must be a positive integer')
    m,b=mapping.copy(),bars.copy()
    m['date']=daily_dates(m.date).to_numpy(); b['date']=daily_dates(b.date).to_numpy()
    m=m.sort_values('date').reset_index(drop=True)
    if m.date.duplicated().any() or b.duplicated(['symbol','date']).any():
        raise ValueError('duplicate mapping or contract bars')
    if m.symbol.isna().any() or len(m) <= map_lag+2:
        raise ValueError('coverage: missing mapping or insufficient history')
    b=b.set_index(['symbol','date'])
    def price(symbol,date,field):
        try:
            value=float(b.loc[(symbol,date),field])
        except KeyError as exc:
            raise ValueError(f'coverage: {symbol} {date.date()} {field} missing') from exc
        if not np.isfinite(value) or value <= 0:
            raise ValueError(f'price must be finite and positive: {symbol} {date} {field}')
        return value
    rows=[]; signal_price=100.; execution_price=100.
    for i in range(map_lag+1,len(m)):
        now,prev=m.date.iloc[i],m.date.iloc[i-1]
        held=m.symbol.iloc[i-1-map_lag]
        signal_contract=m.symbol.iloc[i-map_lag]
        ret=price(held,now,'day_session_open')/price(held,prev,'day_session_open')-1
        signal_ret=price(signal_contract,now,'close')/price(signal_contract,prev,'close')-1
        signal_price*=1+signal_ret; execution_price*=1+ret
        rows.append({'date':now,'entry_date':prev,'map_date':m.date.iloc[i-1-map_lag],
                     'held_contract':held,'signal_contract':signal_contract,
                     'execution_return':ret,'signal_return':signal_ret,
                     'signal_price':signal_price,'execution_price':execution_price})
    return pd.DataFrame(rows)


def trade_costs(weights, contracts, fee_bps, slip_bps):
    w=pd.Series(weights,dtype=float).reset_index(drop=True)
    c=pd.Series(contracts).reset_index(drop=True)
    if len(w)!=len(c) or w.empty or not np.isfinite(w).all() or c.isna().any():
        raise ValueError('Invalid cost inputs')
    if not np.isfinite([fee_bps,slip_bps]).all() or min(fee_bps,slip_bps)<0:
        raise ValueError('Costs must be finite and nonnegative')
    previous=w.shift(1).fillna(0)
    turnover=(w-previous).abs()
    roll=c.ne(c.shift(1))
    turnover.loc[roll]=w.loc[roll].abs()+previous.loc[roll].abs()
    turnover.iloc[-1]+=abs(w.iloc[-1])
    return turnover*fee_bps/10000,turnover*slip_bps/10000,turnover


def replay(indexes, fast, slow, out_dir, fee_bps=4., slip_bps=4.):
    if not 0 < fast < slow:
        raise ValueError('Invalid moving average windows')
    engine=load_frozen_engine(); out=Path(out_dir); out.mkdir(parents=True,exist_ok=True)
    x=indexes.reset_index(drop=True).copy()
    signal=engine.builtin_ma_signal(x[['date','signal_price']].rename(columns={'signal_price':'close'}),fast,slow)
    # Existing run() shifts once; the external signal shifts once as well.
    pd.DataFrame({'date':signal.index,'value':signal.shift(1).to_numpy()}).to_csv(out/'signal.csv',index=False)
    x[['date','execution_price']].rename(columns={'execution_price':'close'}).to_csv(out/'execution_index.csv',index=False)
    cfg=engine.build_parser().parse_args([])
    cfg.demo=False; cfg.prices=str(out/'execution_index.csv'); cfg.signal=str(out/'signal.csv')
    cfg.sizing='fixed_fraction'; cfg.fixed_fraction=.25; cfg.max_weight=.25
    cfg.dd_guard=0.; cfg.stop_pct=0.; cfg.zscore=False; cfg.long_only=False
    cfg.fee_bps=0.; cfg.slip_bps=0.; cfg.out_dir=str(out/'upstream_raw')
    engine.run(cfg)
    curve=pd.read_csv(out/'upstream_raw/equity_curve.csv')
    if len(curve)!=len(x) or not daily_dates(curve.date).equals(daily_dates(x.date)):
        raise ValueError('Frozen engine changed the input calendar')
    x['weight']=curve.weight.to_numpy()
    x['gross_return']=x.weight*x.execution_return
    # Independently reconcile to the engine, not only to our own multiplication.
    np.testing.assert_allclose(curve.ret_net.to_numpy(),x.gross_return.to_numpy(),rtol=1e-10,atol=1e-12)
    x['fee_return'],x['slippage_return'],x['turnover']=trade_costs(x.weight,x.held_contract,fee_bps,slip_bps)
    return x


def training_features(indexes,symbol,start,end):
    x=indexes.copy(); x['date']=pd.to_datetime(x.date)
    # Select the training segment before any rolling calculation.
    p=x.loc[x.date.between(pd.Timestamp(start),pd.Timestamp(end)),'signal_price']
    r=p.pct_change(fill_method=None).dropna()
    if len(r)<60 or not np.isfinite(r).all() or r.std(ddof=1)<=0:
        raise ValueError('Insufficient training features')
    trend=(r.rolling(20).sum().abs()/(r.rolling(20).std(ddof=1)*np.sqrt(20))).dropna()
    result={'symbol':symbol,'feature_start':str(pd.Timestamp(start).date()),'feature_end':str(pd.Timestamp(end).date()),
            'annual_volatility':float(r.std(ddof=1)*np.sqrt(252)),
            'autocorrelation_1':float(r.autocorr(1)),'trend_ratio_20':float(trend.mean())}
    if not np.isfinite([result[k] for k in ('annual_volatility','autocorrelation_1','trend_ratio_20')]).all():
        raise ValueError('Nonfinite training features')
    return result
