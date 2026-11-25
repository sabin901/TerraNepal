import datetime as dt
import unittest
from disaster_lab.direct_ecmwf import utc_cycle, forecast_url, fetch_metadata, SOURCE

class DirectEcmwfTests(unittest.TestCase):
    def test_utc_cycle_validation(self):
        valid = utc_cycle('2026-11-20T00:00:00Z')
        self.assertEqual(valid.hour, 0)
        valid12 = utc_cycle('2026-11-20T12:00:00+00:00')
        self.assertEqual(valid12.hour, 12)
        with self.assertRaises(ValueError):
            utc_cycle('2026-11-20T06:00:00Z') # ECMWF open data is 00z and 12z
        with self.assertRaises(ValueError):
            utc_cycle('2026-11-20T00:15:00Z')

    def test_forecast_url_generation(self):
        url = forecast_url('2026-11-20T00:00:00Z', step=24)
        self.assertIn('20261120/00z', url)
        self.assertIn('24h_oper_0001.grib2', url)

    def test_metadata_envelope(self):
        meta = fetch_metadata('2026-11-20T12:00:00Z', step=48)
        self.assertEqual(meta['source'], SOURCE)
        self.assertEqual(meta['step_hours'], 48)
        self.assertEqual(meta['target_valid_at'], '2026-11-22T12:00:00+00:00')
        self.assertIn('CC BY 4.0', meta['license'])

if __name__ == '__main__':
    unittest.main()
