"""Collect source observations and weather forecasts, reporting partial failures."""
from pathlib import Path
import subprocess
import sys
from weather import ForecastStore
from data import Dataset
from predictions import record_predictions
import json

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    observed=subprocess.run([sys.executable,str(root/'disaster_archive/archive.py'),'collect'],cwd=root)
    print('Collecting ECMWF and NOAA weather outlooks…',flush=True)
    store=ForecastStore(Path(sys.argv[1]) if len(sys.argv)>1 else None)
    outcomes=store.collect()
    for outcome in outcomes: print(outcome,flush=True)
    print('Recording eligible experimental river projections…',flush=True)
    print(json.dumps(record_predictions(Dataset(root),store),indent=2),flush=True)
    failed=observed.returncode!=0 or any(o['status']=='error' or o.get('last_status')=='error' for o in outcomes)
    raise SystemExit(1 if failed else 0)
