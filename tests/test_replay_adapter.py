"""Deterministic test fixtures only, not evidence of market performance."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def adapter():
    path = Path(__file__).parents[1] / 'scripts' / 'replay_adapter.py'
    assert path.exists(), 'Replay adapter is not implemented yet'
    spec = importlib.util.spec_from_file_location('replay_adapter', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(n=400):
    dates = pd.bdate_range('2019-01-01', periods=n)
    maps = pd.DataFrame({'date': dates, 'symbol': ['A']*(n//2)+['B']*(n-n//2)})
    rows = []
    for symbol, scale in [('A', 100.), ('B', 1000.)]:
        for i, date in enumerate(dates):
            price = scale*np.exp(.0005*i+.03*np.sin(i/12))
            rows.append({'date':date, 'symbol':symbol, 'day_session_open':price,
                         'close':price*np.exp(.003*np.cos(i/8)), 'volume':10000.})
    return maps, pd.DataFrame(rows)


def test_contract_level_gap_is_not_a_trading_profit():
    m, bars = fixture(20)
    out = adapter().prepare_indexes(m, bars, map_lag=2)
    assert out.execution_return.abs().max() < .01
    roll = out.index[out.held_contract.ne(out.held_contract.shift())][1]
    prev = out.loc[roll, 'entry_date']
    now = out.loc[roll, 'date']
    b = bars[bars.symbol.eq('B')].set_index('date')
    expected = b.loc[now, 'day_session_open']/b.loc[prev, 'day_session_open']-1
    assert out.loc[roll, 'execution_return'] == pytest.approx(expected)


def test_mapping_is_lagged_before_actual_entry():
    maps, bars = fixture(20)
    out = adapter().prepare_indexes(maps, bars, map_lag=2)
    for row in out.itertuples():
        assert row.map_date < row.entry_date < row.date
        entry_index = list(maps.date).index(row.entry_date)
        assert row.held_contract == maps.iloc[entry_index-2].symbol


def test_missing_selected_contract_bar_is_not_zero_filled():
    m, bars = fixture(20)
    bars = bars[~(bars.symbol.eq('A') & bars.date.eq(m.date.iloc[6]))]
    with pytest.raises(ValueError, match='coverage'):
        adapter().prepare_indexes(m, bars, map_lag=2)


def test_duplicate_or_invalid_prices_are_rejected():
    m, bars = fixture(20)
    with pytest.raises(ValueError, match='duplicate'):
        adapter().prepare_indexes(m, pd.concat([bars,bars.iloc[[5]]]), map_lag=2)
    bars.loc[5,'day_session_open'] = 0
    with pytest.raises(ValueError, match='positive'):
        adapter().prepare_indexes(m, bars, map_lag=2)


def test_roll_both_legs_and_terminal_close_are_charged():
    a = adapter()
    w = pd.Series([.25,.25,-.25,0.])
    contracts = pd.Series(['A','B','B','B'])
    fees, slip, turnover = a.trade_costs(w, contracts, 4, 8)
    np.testing.assert_allclose(turnover, [.25,.5,.5,.25])
    np.testing.assert_allclose(fees, turnover*4/10000)
    np.testing.assert_allclose(slip, turnover*8/10000)
    _,_,last=a.trade_costs(pd.Series([.25,.25]),pd.Series(['A','A']),4,8)
    np.testing.assert_allclose(last, [.25,.25])


def test_future_price_and_map_changes_do_not_change_past_positions(tmp_path):
    a = adapter()
    m,bars = fixture()
    x=a.prepare_indexes(m,bars,2)
    first=a.replay(x,20,60,tmp_path/'first')
    cutoff=m.date.iloc[280]
    changed=bars.copy()
    changed.loc[changed.date>cutoff,['close','day_session_open']]*=3
    m.loc[m.date>cutoff,'symbol']='A'
    second=a.replay(a.prepare_indexes(m,changed,2),20,60,tmp_path/'second')
    cols=['date','weight','gross_return','fee_return','slippage_return']
    pd.testing.assert_frame_equal(first[first.date<=cutoff][cols].reset_index(drop=True),
                                  second[second.date<=cutoff][cols].reset_index(drop=True))


def test_existing_engine_is_hash_verified_and_reused(tmp_path):
    a=adapter()
    m,b=fixture()
    x=a.prepare_indexes(m,b,2)
    result=a.replay(x,20,60,tmp_path)
    engine=a.load_frozen_engine()
    raw=engine.builtin_ma_signal(x.rename(columns={'signal_price':'close'})[['date','close']],20,60)
    expected=engine.target_position(raw,0,0,False).shift(2).fillna(0)*.25
    np.testing.assert_allclose(result.weight,expected)
    np.testing.assert_allclose(result.gross_return,result.weight*x.execution_return)
    assert a.ENGINE_SHA256=='dd5fbaf234c57a08910ffecad80e19c001805328d78fde2b5274741a17946bf5'


def test_features_ignore_future_prices():
    a=adapter(); m,bars=fixture()
    x=a.prepare_indexes(m,bars,2)
    start,end=x.date.iloc[20],x.date.iloc[250]
    original=a.training_features(x,'A',start,end)
    x.loc[x.date>end,'signal_price']*=5
    assert a.training_features(x,'A',start,end)==original
