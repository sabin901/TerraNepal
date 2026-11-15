import copy
import unittest
from weather_evaluation import evaluate

def case():
    common=dict(station_id='S1',variable='temperature_2m',units='degC',period_start='2026-11-02T00:00:00Z',period_end='2026-11-02T00:00:00Z')
    return dict(forecast_origin='2026-11-01T00:00:00Z',mapping=dict(verified=True,station_id='S1',evidence='Synthetic mapping for unit test only'),forecast=dict(common,provider='synthetic',model='test',value=12.,issued_at='2026-10-31T18:00:00Z',retrieved_at='2026-10-31T19:00:00Z'),observation=dict(common,value=10.,quality='verified',available_at='2026-11-02T01:00:00Z'))

def report(cases):return evaluate(dict(schema_version=1,evaluation_as_of='2026-11-03T00:00:00Z',cases=cases))

class WeatherEvaluationTests(unittest.TestCase):
    def test_known_errors_and_distinct_stations(self):
        a,b=case(),case()
        for section in ('forecast','observation','mapping'):b[section]['station_id']='S2'
        b['forecast']['value']=6.
        r=report([a,b]);self.assertEqual(r['matched_cases'],2);self.assertEqual(r['metrics'][0]['mae'],3.);self.assertEqual(r['metrics'][0]['bias'],-1.)
    def test_duplicate_conflicting_truth_excludes_all(self):
        a,b=case(),case();b['observation']['value']=500
        self.assertEqual(report([a,b])['exclusions'],{'duplicate_forecast_target':2})
    def test_missing_nonfinite_and_boolean_not_zero(self):
        for value in [None,float('nan'),float('inf'),True,'12',10**1000]:
            x=case();x['observation']['value']=value
            self.assertEqual(report([x])['exclusions'],{'missing_or_nonfinite_value':1})
        x=case();x['observation']['value']=0
        self.assertEqual(report([x])['matched_cases'],1)
    def test_invalid_contracts(self):
        changes=[('mapping','verified','true','unverified_mapping'),('mapping','evidence','','unverified_mapping'),('observation','station_id','other','station_mismatch'),('observation','units','F','incompatible_units'),('observation','quality','candidate','unverified_observation'),('forecast','retrieved_at','2026-11-01T01:00:00Z','forecast_not_available_at_origin'),('observation','available_at','2026-11-04T01:00:00Z','observation_not_available_at_evaluation'),('forecast','issued_at','2026-10-31T18:00:00','invalid_timestamp'),('observation','period_end','2026-11-02T02:00:00Z','period_mismatch')]
        for section,field,value,reason in changes:
            with self.subTest(reason=reason):
                x=case();x[section][field]=value;self.assertEqual(report([x])['exclusions'],{reason:1})
    def test_timezone_equivalence(self):
        x=case()
        for k in ('period_start','period_end'):x['observation'][k]='2026-11-02T05:45:00+05:45'
        self.assertEqual(report([x])['matched_cases'],1)
    def test_rain_requires_positive_matching_accumulation(self):
        x=case()
        for section in ('forecast','observation'):x[section].update(variable='precipitation',units='mm')
        self.assertEqual(report([x])['exclusions'],{'invalid_period':1})
        for section in ('forecast','observation'):x[section]['period_start']='2026-11-01T21:00:00Z'
        self.assertEqual(report([x])['metrics'][0]['period_hours'],3.)
    def test_no_input_mutation(self):
        x=case();before=copy.deepcopy(x);report([x]);self.assertEqual(x,before)
    def test_empty_not_zero_error_score(self):
        self.assertEqual(report([])['metrics'],[])
    def test_provider_groups_and_wind_not_gust(self):
        a,b=case(),case();b['forecast']['provider']='other'
        self.assertEqual(len(report([a,b])['metrics']),2)
        a['forecast']['variable']='wind_gusts_10m'
        self.assertEqual(report([a])['exclusions'],{'unsupported_variable':1})

if __name__=='__main__':unittest.main()
