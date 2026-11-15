import csv,io,unittest
import ghcnh

class GHCNhTemperature(unittest.TestCase):
    def parse(self,**changes):
        row={'STATION':'NPI0000VNKT','DATE':'2026-11-01T12:00:00','LATITUDE':'27.6966',
             'LONGITUDE':'85.3592','ELEVATION':'1338.1','temperature':'0.0',
             'temperature_Quality_Code':'1','temperature_Source_Code':'223','temperature_Measurement_Code':''}
        row.update(changes);s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(row),delimiter='|');w.writeheader();w.writerow(row)
        return ghcnh.normalize(s.getvalue().encode(),'2026-11-15T00:00:00Z')[0]
    def test_real_zero_and_utc_and_no_tenths_rescaling(self):
        self.assertTrue(self.parse()['eligible_temperature']);self.assertEqual(self.parse()['value'],0)
        self.assertEqual(self.parse(temperature='16.4')['value'],16.4)
        self.assertEqual(self.parse()['observed_at'],'2026-11-01T12:00:00+00:00')
    def test_missing_never_becomes_zero(self):
        r=self.parse(temperature='');self.assertIsNone(r['value']);self.assertFalse(r['eligible_temperature'])
    def test_unknown_suspect_and_blank_flags_remain_excluded(self):
        for qc in ['','2','1s','4']:
            self.assertFalse(self.parse(temperature_Quality_Code=qc)['eligible_temperature'])
        self.assertFalse(self.parse(temperature_Source_Code='999')['eligible_temperature'])
    def test_bad_metadata_or_future_time_excluded(self):
        for changes in [{'LATITUDE':'nan'},{'ELEVATION':'-999.9'},{'DATE':'2026-12-01T00:00:00'},{'STATION':'XXI0000VNKT'},{'temperature':'NaN'}]:
            self.assertFalse(self.parse(**changes)['eligible_temperature'])
