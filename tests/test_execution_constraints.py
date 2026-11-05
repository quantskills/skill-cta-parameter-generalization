"""Hypothetical fill scenarios, not historical execution evidence."""
import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import pytest

def module():
    p = Path(__file__).parents[1] / 'scripts/execution_constraints.py'
    assert p.exists(), 'constraint replay missing'
    s = importlib.util.spec_from_file_location('constraints', p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m

def case():
    return {'initial_capital': 10000, 'fee_per_lot': 2, 'slippage': 0,
            'rows': [dict(contract='TEST01', decision_at='2025-01-02T08:59:00+08:00',
             target_at='2025-01-01T16:00:00+08:00', open_at='2025-01-02T09:00:00+08:00',
             close_at='2025-01-02T15:00:00+08:00', rule_available_at='2025-01-01T16:00:00+08:00',
             capacity_available_at='2025-01-01T16:00:00+08:00', target_lots=2.9,
             open=100, close=110, multiplier=10, margin_rate=.1,
             lower_limit=80, upper_limit=120, capacity_lots=100)]}

def nextrow(first, **updates):
    r = copy.deepcopy(first)
    for k in ('decision_at', 'open_at', 'close_at'):
        r[k] = r[k].replace('2025-01-02', '2025-01-03')
    r.update(updates)
    return r

def test_rounding_and_marked_equity():
    r = module().replay(case())['ledger'][0]
    assert r['position'] == 2
    assert r['fees'] == 4
    assert r['equity'] == 10196

def test_margin_limits_openings():
    c = case(); c['initial_capital'] = 250; c['rows'][0]['target_lots'] = 100
    r = module().replay(c)['ledger'][0]
    assert r['position'] == 2
    assert 'margin_limited' in r['events']

def test_blocked_exit_carries_position():
    c = case(); c['rows'].append(nextrow(c['rows'][0], target_lots=0, open=80, close=80))
    r = module().replay(c)['ledger'][-1]
    assert r['position'] == 2 and r['filled_delta'] == 0
    assert r['equity'] == 9596
    assert 'limit_blocked' in r['events']

def test_roundtrip_fees_and_realized_reconcile():
    c = case(); c['rows'].append(nextrow(c['rows'][0], target_lots=0, open=110, close=110))
    out = module().replay(c); r = out['ledger'][-1]
    assert r['realized_pnl'] == 200 and r['unrealized_pnl'] == 0
    assert r['equity'] == 10192 and out['total_fees'] == 8

def test_capacity_and_slippage():
    c=case(); c['slippage']=1; c['rows'][0]['capacity_lots']=1
    r=module().replay(c)['ledger'][0]
    assert r['position']==1 and r['fill_price']==101 and r['equity']==10088
    c['slippage']=21
    assert module().replay(c)['ledger'][0]['position']==0

def test_future_values_do_not_change_past():
    c=case(); c['rows'].append(nextrow(c['rows'][0], close=115))
    first=module().replay(c)['ledger'][0]
    c['rows'][1].update(target_lots=-5, close=85)
    assert module().replay(c)['ledger'][0]==first

@pytest.mark.parametrize('field,value', [('target_lots',True),('capacity_lots',1.5),('margin_rate',0),('multiplier',float('nan')),('open',121),('rule_available_at','2026-01-01T00:00:00+08:00'),('target_at','2025-01-02T09:01:00+08:00')])
def test_invalid_and_future_inputs_fail(field,value):
    c=case(); c['rows'][0][field]=value
    with pytest.raises(ValueError): module().replay(c)

def test_missing_rule_fails_but_missing_publication_is_labeled():
    c=case(); del c['rows'][0]['margin_rate']
    with pytest.raises(ValueError): module().replay(c)
    c=case(); c['rows'][0]['rule_available_at']=None
    out=module().replay(c)
    assert out['evidence_status']=='assumption_only' and not out['executable']

def test_contract_switch_rejected():
    c=case(); c['rows'].append(nextrow(c['rows'][0], contract='OTHER'))
    with pytest.raises(ValueError): module().replay(c)

def test_margin_breach_not_silent_liquidation():
    c=case(); c['initial_capital']=250
    c['rows'].append(nextrow(c['rows'][0], target_lots=5, open=81, close=81))
    r=module().replay(c)['ledger'][-1]
    assert r['position']==2 and r['margin_breach']
    assert 'margin_breach_no_new_open' in r['events']

def test_opening_deficit_recorded_even_when_close_recovers():
    c=case(); c['initial_capital']=250
    c['rows'].append(nextrow(c['rows'][0], target_lots=2, open=90, close=110))
    r=module().replay(c)['ledger'][-1]
    assert 'margin_breach_at_open' in r['events']
    assert r['margin_breach_at_open'] is True
    assert r['margin_breach'] is False

def test_zero_slipped_price_not_filled():
    c=case(); c['slippage']=100
    c['rows'][0].update(lower_limit=0, target_lots=-1)
    r=module().replay(c)['ledger'][0]
    assert r['position']==0 and 'limit_blocked' in r['events']

@pytest.mark.parametrize('capital', [250, 1000, 10000])
@pytest.mark.parametrize('fee,slip,capacity', [(0,0,100),(2,1,1),(4,2,3)])
def test_stress_grid_reconciles_every_ledger_row(capital,fee,slip,capacity):
    c=case(); c.update(initial_capital=capital,fee_per_lot=fee,slippage=slip)
    c['rows'][0].update(target_lots=20,capacity_lots=capacity)
    c['rows'].append(nextrow(c['rows'][0], target_lots=-20,open=105,close=90))
    c['rows'].append({**nextrow(c['rows'][1], target_lots=0,open=95,close=95),
        'decision_at':'2025-01-04T08:59:00+08:00','open_at':'2025-01-04T09:00:00+08:00','close_at':'2025-01-04T15:00:00+08:00'})
    # Dates form hypothetical sessions; this is not an exchange calendar.
    for row in module().replay(c)['ledger']:
        assert row['equity']==pytest.approx(capital+row['realized_pnl']+row['unrealized_pnl']-row['total_fees'])
        assert abs(row['filled_delta'])<=capacity
        assert row['fees']==abs(row['filled_delta'])*fee

def test_real_cli_no_overwrite_and_invalid_no_output(tmp_path):
    source=tmp_path/'输入.json'; source.write_text(json.dumps(case()),encoding='utf-8')
    out=tmp_path/'中文 result'
    cmd=[sys.executable,'-X','utf8',str(Path(__file__).parents[1]/'scripts/execution_constraints.py'),'--input',str(source),'--output',str(out)]
    assert subprocess.run(cmd,capture_output=True).returncode==0
    before={p.name:p.read_bytes() for p in out.iterdir()}
    assert '使用结果.md' in before and 'ledger.csv' in before
    assert subprocess.run(cmd,capture_output=True).returncode!=0
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}
    c=case(); del c['rows'][0]['margin_rate']
    source.write_text(json.dumps(c),encoding='utf-8')
    bad=tmp_path/'invalid'
    assert subprocess.run(cmd[:-1]+[str(bad)],capture_output=True).returncode!=0
    assert not bad.exists()
