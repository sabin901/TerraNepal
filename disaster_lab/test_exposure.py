"""Synthetic geometry/lineage fixtures, not real hazards or asset coverage."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import exposure as e

AT='2026-11-15T12:00:00Z'

def provenance():
    return dict(source_id='synthetic-test',source_version='fixture-1',evidence_id='evidence-test',sha256='a'*64,
                as_of='2026-11-15T10:00:00Z',acquired_at='2026-11-15T11:00:00Z')

def box(x=80,y=26,size=2):
    return [[x,y],[x+size,y],[x+size,y+size],[x,y+size],[x,y]]

def hazards():
    return {'type':'FeatureCollection','features':[{'type':'Feature','id':'test-extent',
        'geometry':{'type':'Polygon','coordinates':[box()]},'properties':{
        'evidence':provenance(),'kind':'scenario','valid_from':'2026-11-15T12:00:00Z','valid_until':'2026-11-16T12:00:00Z'}}]}

def assets(points=((81,27),)):
    return {'type':'FeatureCollection','features':[{'type':'Feature','id':f'test-asset-{i}',
        'geometry':{'type':'Point','coordinates':list(p)},'properties':{'evidence':provenance(),'sector':'health'}} for i,p in enumerate(points)]}


class ExposureTests(unittest.TestCase):
    def test_inside_outside_boundary_and_no_damage_claim(self):
        r=e.assess(hazards(),assets(((81,27),(83,27),(80,27))),AT)
        self.assertEqual([a['status'] for a in r['assets']],['intersects_supplied_extent','no_intersection_in_supplied_footprints','intersects_supplied_extent'])
        self.assertEqual(r['assets'][2]['matches'][0]['relation'],'boundary')
        self.assertTrue(all(a['damage_assessment']=='not_established' and a['safety_assessment']=='not_established' for a in r['assets']))

    def test_hole_interior_excluded_boundary_included(self):
        h=hazards();h['features'][0]['geometry']['coordinates'].append(box(80.5,26.5,1))
        r=e.assess(h,assets(((81,27),(80.5,27),(80.2,26.2))),AT)
        self.assertFalse(r['assets'][0]['matches']);self.assertEqual(r['assets'][1]['matches'][0]['relation'],'boundary')
        self.assertEqual(r['assets'][2]['matches'][0]['relation'],'inside')

    def test_ring_orientation_does_not_change_intersection(self):
        h=hazards();a=e.assess(h,assets(),AT)
        h['features'][0]['geometry']['coordinates'][0].reverse()
        b=e.assess(h,assets(),AT)
        self.assertEqual(a['assets'],b['assets']);self.assertNotEqual(a['input_sha256'],b['input_sha256'])

    def test_multipolygon_and_island_in_hole(self):
        h=hazards();g=h['features'][0]['geometry'];g['type']='MultiPolygon'
        g['coordinates']=[[box(),box(80.5,26.5,1)],[box(80.8,26.8,.2)]]
        r=e.assess(h,assets(((80.9,26.9),(81.3,27.3))),AT)
        self.assertTrue(r['assets'][0]['matches']);self.assertFalse(r['assets'][1]['matches'])

    def test_invalid_holes_and_overlapping_components(self):
        for hole in (box(83,26,1),box(79.5,26.5,1),box(80,26.5,1)):
            h=hazards();h['features'][0]['geometry']['coordinates'].append(hole)
            with self.assertRaises(ValueError):e.assess(h,assets(),AT)
        h=hazards();h['features'][0]['geometry']={'type':'MultiPolygon','coordinates':[[box()],[box(81,27,2)]]}
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)

    def test_self_intersection_degenerate_and_duplicate_vertices(self):
        for ring in ([[80,26],[82,28],[80,28],[82,26],[80,26]],
                     [[80,26],[81,26],[82,26],[80,26]],
                     [[80,26],[82,26],[82,28],[82,26],[80,26]]):
            h=hazards();h['features'][0]['geometry']['coordinates']=[ring]
            with self.assertRaises(ValueError):e.assess(h,assets(),AT)

    def test_adjacent_reversal_rejected_collinear_extension_allowed(self):
        h=hazards();h['features'][0]['geometry']['coordinates']=[[[80,26],[82,26],[81,26],[82,28],[80,28],[80,26]]]
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)
        h['features'][0]['geometry']['coordinates']=[[[80,26],[81,26],[82,26],[82,28],[80,28],[80,26]]]
        self.assertTrue(e.assess(h,assets(),AT)['assets'][0]['matches'])

    def test_antimeridian_polar_altitude_nonfinite_and_crs_rejected(self):
        h=hazards();h['features'][0]['geometry']['coordinates']=[[[179,26],[-179,26],[-179,28],[179,28],[179,26]]]
        with self.assertRaisesRegex(ValueError,'Antimeridian'):e.assess(h,assets(),AT)
        for coordinate in ([80,float('nan')],[True,27],[81,27,30],[180.1,27],[10**1000,27]):
            a=assets();a['features'][0]['geometry']['coordinates']=coordinate
            with self.assertRaises(ValueError):e.assess(hazards(),a,AT)
        h=hazards();h['crs']={'name':'EPSG:3857'}
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)
        h=hazards();h['features'][0]['geometry']['coordinates']=[box(80,81)]
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)

    def test_duplicate_ids_rejected(self):
        for kind in ('hazards','assets'):
            h=hazards();a=assets();doc=h if kind=='hazards' else a
            doc['features'].append(copy.deepcopy(doc['features'][0]))
            with self.assertRaisesRegex(ValueError,'duplicate'):e.assess(h,a,AT)

    def test_no_future_evidence_and_no_naive_dates(self):
        for field,value in (('acquired_at','2026-11-15T12:00:01Z'),('as_of','2026-11-15T11:00:01Z'),('as_of','2026-11-15T10:00:00')):
            a=assets();a['features'][0]['properties']['evidence'][field]=value
            with self.assertRaises(ValueError):e.assess(hazards(),a,AT)
        with self.assertRaises(ValueError):e.assess(hazards(),assets(),'bad')

    def test_observed_vs_scenario_and_target_date(self):
        h=hazards();h['features'][0]['properties']['kind']='observed_extent'
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)
        h['features'][0]['properties']['valid_from']='2026-11-15T10:00:00Z'
        with self.assertRaisesRegex(ValueError,'after its acquisition'):e.assess(h,assets(),AT)
        h['features'][0]['properties']['valid_until']='2026-11-15T11:00:00Z'
        r=e.assess(h,assets(),AT,'2026-11-15T10:30:00Z')
        self.assertEqual(r['assets'][0]['matches'][0]['kind'],'observed_extent')
        r=e.assess(h,assets(),AT,'2026-11-16T12:00:00Z')
        self.assertEqual(r['assets'][0]['status'],'unassessed')
        self.assertEqual(r['excluded_footprints'][0]['reason'],'outside_validity_interval')

    def test_later_asset_inventory_does_not_establish_historical_exposure(self):
        h=hazards();h['features'][0]['properties']['valid_from']='2026-11-14T00:00:00Z'
        r=e.assess(h,assets(),AT,'2026-11-14T12:00:00Z')
        self.assertEqual(r['assets'][0]['status'],'unassessed')
        self.assertEqual(r['assets'][0]['unassessed_reason'],'asset_record_postdates_target')
        self.assertEqual(r['assets'][0]['matches'],[])

    def test_empty_coverage_not_safe(self):
        r=e.assess({'type':'FeatureCollection','features':[]},assets(),AT)
        self.assertEqual(r['assets'][0]['status'],'unassessed')
        self.assertEqual(r['assets'][0]['safety_assessment'],'not_established')

    def test_replay_digest_and_mutation(self):
        h=hazards();a=assets();r=e.assess(h,a,AT)
        self.assertEqual(r,e.assess(json.loads(json.dumps(h)),a,AT))
        self.assertEqual(h,hazards())
        a['features'][0]['properties']['evidence']['source_version']='fixture-2'
        self.assertNotEqual(r['assessment_id'],e.assess(h,a,AT)['assessment_id'])

    def test_missing_hash_and_unknown_geometry_rejected(self):
        a=assets();a['features'][0]['properties']['evidence']['sha256']='not-a-hash'
        with self.assertRaises(ValueError):e.assess(hazards(),a,AT)
        h=hazards();h['features'][0]['geometry']['type']='LineString'
        with self.assertRaises(ValueError):e.assess(h,assets(),AT)

    def test_cli_refuses_evidence_overwrite_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);h=root/'hazards.json';a=root/'assets.json';o=root/'result.json'
            h.write_text(json.dumps(hazards()));a.write_text(json.dumps(assets()));before=h.read_bytes()
            cmd=[sys.executable,e.__file__,'--hazards',str(h),'--assets',str(a),'--at',AT,'--output']
            self.assertNotEqual(subprocess.run(cmd+[str(h)],capture_output=True).returncode,0)
            self.assertEqual(h.read_bytes(),before)
            self.assertEqual(subprocess.run(cmd+[str(o)],capture_output=True).returncode,0)
            self.assertEqual(json.loads(o.read_text()),e.assess(hazards(),assets(),AT))
            self.assertNotEqual(subprocess.run(cmd+[str(o)],capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
