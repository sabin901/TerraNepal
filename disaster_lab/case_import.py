"""Import dated public weather evidence into private review cases; never incidents."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'public_site'))
from intelligence import brief
from weather import PLACES
from cases import CaseStore


def unreviewed(reason):
    return {'status':'unverified','reviewer':None,'reviewed_at':None,'reason':reason}


def import_weather(snapshot, store, at=None):
    cutoff=store.clock() if at is None else at
    assessment=brief(snapshot,cutoff)
    revisions=[]
    for place in PLACES:
        sources=[w for w in snapshot['weather'] if w['place_id']==place['id']]
        if not sources:continue
        summaries=[w for w in assessment['weather'] if w['place_id']==place['id']]
        evidence=[{'kind':'provider_forecast','source':'Open-Meteo / '+w['model'],
                   'source_url':'https://api.open-meteo.com/v1/forecast','sha256':w['sha256'],
                   'acquired_at':w['fetched_at'],
                   'valid_from':w['normalized']['points'][0]['at'],'valid_to':w['normalized']['points'][-1]['at'],
                   'review':unreviewed('Model output reference; local forecast skill and station mapping not independently verified.')} for w in sources]
        document={'title':place['name']+' weather evidence review','hazard':'weather',
                  'geography':{'type':'point','coordinates':[place['longitude'],place['latitude']],
                               'label':place['name']+' illustrative city point',
                               'review':unreviewed('Requested city point, not an approved station, ward or catchment mapping.')},
                  'valid_from':assessment['weather_window']['start'],'valid_to':assessment['weather_window']['end'],
                  'summary':'Dated weather review, not a reported disaster or warning. Brief '+assessment['brief_id']+
                            '. Availability '+assessment['availability']['status']+'. Model-specific summaries: '+json.dumps(summaries,ensure_ascii=False,separators=(',',':')),
                  'evidence':evidence}
        case_id='weather-'+place['id']+'-'+assessment['weather_window']['start'][:10]
        revisions.append(store.append_revision(case_id,document))
    return {'case_ids':[r['case_id'] for r in revisions], 'revisions':[r['sha256'] for r in revisions],
            'brief_id':assessment['brief_id'],'scope':'Private weather review cases; no new incident, official warning or verified impact inferred.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('snapshot',type=Path);p.add_argument('--state',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(import_weather(json.loads(a.snapshot.read_text()),CaseStore(a.state)),indent=2))

if __name__=='__main__':main()
