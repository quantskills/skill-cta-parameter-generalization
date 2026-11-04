"""Bounded read-only PandaData collection in an already authorized EVO project.

Does not log in, read credential files, alter endpoints, or place orders.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import inspect
import json
from pathlib import Path
import pandas as pd


def date_windows(start,end):
    first,last=pd.Timestamp(start),pd.Timestamp(end)
    if first>last:
        raise ValueError('Invalid date range')
    result=[]
    while first<=last:
        stop=min(pd.Timestamp(year=first.year+4,month=12,day=31),last)
        result.append((first.strftime('%Y%m%d'),stop.strftime('%Y%m%d')))
        first=stop+pd.Timedelta(days=1)
    return result


def bar_jobs(mapping,windows,batch_size=24):
    if not 1<=batch_size<=40:
        raise ValueError('Bounded batch size required')
    m=mapping.copy(); m['date']=pd.to_datetime(m.date.astype(str),format='%Y%m%d')
    result=[]
    for start,end in windows:
        lookback=pd.Timestamp(start)-pd.Timedelta(days=30)
        symbols=sorted(m.loc[m.date.between(lookback,pd.Timestamp(end)),'symbol'].unique())
        for offset in range(0,len(symbols),batch_size):
            result.append({'symbol':symbols[offset:offset+batch_size],'start_date':start,'end_date':end})
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_row_count(count):
    # Heuristic only: other truncation points still require source/calendar checks.
    if count in (10000, 50000, 100000):
        raise ValueError('Possible row limit: stop and use a newly frozen smaller collection batch')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--output',required=True)
    p.add_argument('--phase',required=True,choices=['maps','bars'])
    p.add_argument('--offset',type=int,default=0);p.add_argument('--limit',type=int,default=4)
    a=p.parse_args()
    if a.offset<0 or not 1<=a.limit<=8:
        raise ValueError('Request at most eight batches per invocation')
    import panda_data
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8'))
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    lock=out/'collection-input.json'
    frozen={'config_sha256':digest(a.config),'windows':date_windows(cfg['data_start'],cfg['test_end']),
            'symbols':cfg['train_symbols']+cfg['holdout_symbols']}
    normalized=json.loads(json.dumps(frozen))
    if lock.exists() and json.loads(lock.read_text(encoding='utf-8'))!=normalized:
        raise ValueError('Collection configuration drift')
    if not lock.exists():lock.write_text(json.dumps(frozen,indent=2),encoding='utf-8')
    docs=out/'sdk-methods.json'
    if not docs.exists():
        docs.write_text(json.dumps({name:{'signature':str(inspect.signature(getattr(panda_data,name))),
                   'doc':inspect.getdoc(getattr(panda_data,name))} for name in ('get_future_dominant','get_future_daily')},ensure_ascii=False,indent=2),encoding='utf-8')
    ledger=out/'requests.jsonl'
    old=[json.loads(line) for line in ledger.read_text(encoding='utf-8').splitlines()] if ledger.exists() else []
    def fetch(key,name,params):
        path=out/(key+'.csv')
        prior=[r for r in old if r['key']==key]
        if prior:
            if len(prior)!=1 or prior[0]['params']!=params or not path.exists() or digest(path)!=prior[0]['sha256']:
                raise ValueError('Cached data or parameters changed')
            validate_row_count(prior[0]['rows'])
            return pd.read_csv(path,dtype={'date':str})
        if path.exists():raise ValueError('Unindexed artifact found; inspect before retrying')
        data=getattr(panda_data,name)(**params)
        if not isinstance(data,pd.DataFrame) or data.empty:raise ValueError(f'Empty data: {key}')
        if not {'date','symbol'}<=set(data):raise ValueError(f'Missing data keys: {key}')
        validate_row_count(len(data))
        data.to_csv(path,index=False)
        row={'key':key,'method':name,'params':params,'rows':len(data),'columns':list(data),
             'sha256':digest(path),'at':datetime.now(timezone.utc).isoformat(),
             'possible_row_limit':len(data) in (10000,50000,100000)}
        with ledger.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
        print(json.dumps({'query':key,'rows':len(data),'sha256':row['sha256']},ensure_ascii=False),flush=True)
        return data
    if a.phase=='maps':
        maps=[]
        for i,(start,end) in enumerate(frozen['windows']):
            maps.append(fetch(f'maps-{i:02d}','get_future_dominant',{
                'underlying_symbol':frozen['symbols'],'start_date':start,'end_date':end}))
        m=pd.concat(maps,ignore_index=True)
        if m.duplicated(['underlying_symbol','date']).any() or set(m.underlying_symbol)!=set(frozen['symbols']):
            raise ValueError('Missing symbols or duplicate mapping dates')
        m.to_csv(out/'mapping.csv',index=False)
        jobs=bar_jobs(m,frozen['windows'])
        (out/'bar-jobs.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'phase':'maps','rows':len(m),'bar_batches':len(jobs),'mapping_sha256':digest(out/'mapping.csv')}),flush=True)
    else:
        m=pd.read_csv(out/'mapping.csv',dtype={'date':str})
        jobs=bar_jobs(m,frozen['windows'])
        if json.loads((out/'bar-jobs.json').read_text(encoding='utf-8'))!=jobs:
            raise ValueError('Bar collection plan changed')
        for i in range(a.offset,min(a.offset+a.limit,len(jobs))):
            fetch(f'bars-{i:04d}','get_future_daily',jobs[i])
        completed={r['key'] for r in old if r['key'].startswith('bars-')}
        print(json.dumps({'phase':'bars','requested_offset':a.offset,'requested_limit':a.limit,'total_batches':len(jobs)}),flush=True)


if __name__=='__main__':main()
