import importlib.util
from pathlib import Path
import pandas as pd

def collector():
    p=Path(__file__).parents[1]/'scripts/collect_pandadata.py'
    assert p.exists(), 'Data collector is not implemented'
    spec=importlib.util.spec_from_file_location('collector',p)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_date_windows_never_exceed_five_years():
    assert collector().date_windows('2015-01-01','2025-12-31')==[
        ('20150101','20191231'),('20200101','20241231'),('20250101','20251231')]

def test_contract_jobs_include_prior_mapping_at_window_boundary():
    maps=pd.DataFrame({'date':['20191230','20200102','20200103'],'symbol':['A1912.X','A2001.X','A2002.X']})
    jobs=collector().bar_jobs(maps,[('20200101','20201231')],batch_size=2)
    assert jobs==[{'symbol':['A1912.X','A2001.X'],'start_date':'20200101','end_date':'20201231'},
                  {'symbol':['A2002.X'],'start_date':'20200101','end_date':'20201231'}]
def test_suspected_row_caps_are_blocked():
    import collect_pandadata
    import pytest
    for count in (10000, 50000, 100000):
        with pytest.raises(ValueError, match='row limit'):
            collect_pandadata.validate_row_count(count)
    collect_pandadata.validate_row_count(9999)

