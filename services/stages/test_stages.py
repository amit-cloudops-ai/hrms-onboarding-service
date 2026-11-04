import os, unittest
from unittest.mock import Mock, patch
from services.stages.handler import lambda_handler, process_stage, record_policy_acceptance
from services.stages.stages import STAGES, STATUSES, WP4_STAGES
def event(stage="it_provisioning",**overrides):
    value={"action":"execute_stage","employee_id":"EMP001","stage":stage,"mode":"simulated","correlation_id":"exec-123-stage-"+stage}; value.update(overrides); return value
class TestWP4BusinessAdapter(unittest.TestCase):
    def test_wp4_business_stages_exclude_human_policy_signoff(self): self.assertEqual(WP4_STAGES,("it_provisioning","manager_intro"))
    def test_direct_json_contract(self):
        result=process_stage(event(),"simulated"); self.assertTrue(result["ok"]); self.assertEqual(result["status"],"complete"); self.assertEqual(result["result"]["equipment_status"],"assigned")
    def test_manager_intro(self): self.assertEqual(process_stage(event("manager_intro"),"simulated")["result"]["invitation_status"],"created")
    def test_policy_signoff_not_automatic(self):
        with self.assertRaisesRegex(ValueError,"does not execute"): process_stage(event("policy_signoff"),"simulated")
    def test_real_mode_fails_closed(self):
        with self.assertRaises(NotImplementedError): process_stage(event(mode="real"),"real")
    def test_mode_must_match(self):
        with self.assertRaisesRegex(ValueError,"does not match"): process_stage(event(mode="real"),"simulated")
    @patch.dict(os.environ,{"MODE":"simulated"},clear=True)
    def test_lambda_returns_direct_object(self): self.assertNotIn("statusCode",lambda_handler(event(),None))
    @patch.dict(os.environ,{},clear=True)
    def test_missing_mode_fails_closed(self): self.assertFalse(lambda_handler(event(),None)["ok"])
class TestPolicyAcceptance(unittest.TestCase):
    def setUp(self):
        self.event={"action":"sign_policy","employee_id":"EMP001","caller":{"sub":"cognito-sub-1"},"policy":{"policy_id":"company_policy","version":"v1","accepted":True}}
        self.table=Mock(); self.table.get_item.return_value={"Item":{}}
    def test_records_acceptance_without_lifecycle_update(self):
        result=record_policy_acceptance(self.event,table=self.table,now="2026-11-03T12:00:00Z")
        kw=self.table.update_item.call_args.kwargs
        self.assertEqual(result["status"],"accepted"); self.assertIn("policy_accepted",kw["UpdateExpression"]); self.assertNotIn("#status",kw["UpdateExpression"])
    def test_requires_cognito_sub(self):
        with self.assertRaisesRegex(ValueError,"Cognito subject"): record_policy_acceptance({**self.event,"caller":{}},table=self.table)
    def test_requires_explicit_acceptance(self):
        with self.assertRaisesRegex(ValueError,"Explicit"): record_policy_acceptance({**self.event,"policy":{**self.event["policy"],"accepted":False}},table=self.table)
    def test_idempotent(self):
        self.table.get_item.return_value={"Item":{"policy_id":"company_policy","policy_version":"v1","policy_accepted":True,"policy_accepted_by":"cognito-sub-1"}}
        result=record_policy_acceptance(self.event,table=self.table); self.assertTrue(result["already_accepted"]); self.table.update_item.assert_not_called()
if __name__=="__main__": unittest.main()
