import json,unittest
from validator_diagnostics import diagnostic
class DiagnosticTests(unittest.TestCase):
 def test_missing_resource(self):
  d=diagnostic(json.dumps({'format':'Microsoft Tokens.xml folder','stage':'resource-validation','code':'missing-resource','errorClass':'ModelValidationException','message':'untrusted','missingResources':['2052.BR0']}),1)
  self.assertEqual(['2052.BR0'],d['missingResources']);self.assertIn('обязательный',d['reason']);self.assertEqual('resource-validation',d['stage'])
 def test_secrets_and_absolute_paths_not_repeated(self):
  secret='Bearer PRIVATE_SECRET password=hidden /private/workspace/key'
  d=diagnostic(json.dumps({'message':secret,'errorClass':secret,'stage':secret,'code':secret,'format':secret,'missingResources':['/private/device/2052.BR3','license-secret.txt']}),1)
  value=json.dumps(d);self.assertNotIn('PRIVATE_SECRET',value);self.assertNotIn('/private',value);self.assertNotIn('password=',value);self.assertEqual(['2052.BR3'],d['missingResources'])
 def test_unstructured_stderr_hidden(self):
  d=diagnostic('Exception in thread main: token=private\n/private/somewhere',7);self.assertEqual(7,d['exitCode']);self.assertNotIn('private',json.dumps(d))
if __name__=='__main__':unittest.main()
