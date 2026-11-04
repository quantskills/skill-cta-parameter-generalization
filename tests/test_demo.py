import json
from pathlib import Path
import subprocess
import sys


def test_demo_runs_without_credentials_and_preserves_results(tmp_path):
    script = Path(__file__).parents[1] / 'scripts' / 'demo.py'
    out = tmp_path / 'demo'
    proc = subprocess.run([sys.executable, str(script), '--output', str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    report = json.loads((out / 'analysis' / 'report.json').read_text('utf-8'))
    assert len(report['metrics']) == 24
    assert json.loads((out / 'example-info.json').read_text())['synthetic'] is True
    before = (out / 'analysis' / 'report.json').read_bytes()
    again = subprocess.run([sys.executable, str(script), '--output', str(out)], capture_output=True)
    assert again.returncode != 0
    assert (out / 'analysis' / 'report.json').read_bytes() == before
