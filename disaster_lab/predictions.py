"""Record eligible short-horizon projections after an observation refresh."""
import collections
import json
from pathlib import Path
import sys
from analytics import analyze
from data import Dataset, now
from weather import ForecastStore
from verification import verify

def record_predictions(dataset, store, horizons=(30,60,180)):
    dataset.ensure();counts=collections.Counter();by_horizon={}
    for horizon in horizons:
        available=withheld=0
        for sid,rows in dataset.river_groups.items():
            result=analyze(rows,horizon)
            if result['projection'] and store.save_river(sid,result): available+=1
            else:withheld+=1
        by_horizon[str(horizon)]={'eligible_saved_or_already_present':available,'withheld':withheld}
        counts['eligible_saved_or_already_present']+=available;counts['withheld']+=withheld
    verification=verify(store,dataset)
    return {'verification':verification,'finished_at':now(),'horizons_minutes':by_horizon,**counts,
            'note':'Source-level research projections only. Eligibility is not validated warning accuracy.'}

if __name__=='__main__':
    print(json.dumps(record_predictions(Dataset(),ForecastStore(Path(sys.argv[1]) if len(sys.argv)>1 else None)),indent=2))
