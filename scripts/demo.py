"""Offline synthetic input example, not a market backtest or platform receipt."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    out = Path(parser.parse_args().output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    rows = []
    for j, symbol in enumerate('ABCDE'):
        for i, date in enumerate(pd.bdate_range('2024-01-01', periods=50)):
            for parameter in ('10', '20', '40'):
                rows.append(dict(date=date, symbol=symbol, parameter=parameter,
                                 gross_return=.001*(1+int(parameter)/40)+np.sin(i+j)*.003,
                                 fee_return=.0001, slippage_return=.0001))
    pd.DataFrame(rows).to_csv(out/'outcomes.csv', index=False)
    pd.DataFrame(dict(symbol=list('ABCDE'), feature_start='2024-01-01',
                      feature_end='2024-02-01', vol=[1, 1.1, 4, 4.1, 2])).to_csv(out/'features.csv', index=False)
    cfg = dict(train_start='2024-01-01', train_end='2024-02-02', test_end='2024-03-15',
               train_symbols=list('ABCD'), holdout_symbols=['E'], parameters=['10','20','40'],
               baseline_parameter='20', feature_columns=['vol'], clusters=2, seed=42)
    (out/'config.json').write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    (out/'example-info.json').write_text(json.dumps({'synthetic': True, 'network_used': False,
        'purpose': 'CLI demonstration only; no market or platform evidence'}), encoding='utf-8')
    command = [sys.executable, '-X', 'utf8', str(Path(__file__).with_name('analyze.py'))]
    for key in ('outcomes', 'features', 'config'):
        command.extend(['--'+key, str(out/(key+('.json' if key=='config' else '.csv')))])
    subprocess.run(command+['--output', str(out/'analysis')], check=True)
    print('SYNTHETIC DEMO ONLY:', out)


if __name__ == '__main__':
    main()
