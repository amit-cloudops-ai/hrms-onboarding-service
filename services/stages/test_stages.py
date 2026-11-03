import os
import unittest
from unittest.mock import patch
from services.stages.handler import lambda_handler, process_stage
from services.stages.stages import STAGES, STATUSES, WP4_STAGES

def event(stage="it_provisioning", **overrides):
    value = {"action":"execute_stage","employee_id":"EMP001","stage":stage,"mode":"simulated","correlation_id":"exec-123-stage-"+stage}
    value.update(overrides)
    return value

class TestWP4BusinessAdapter(unittest.TestCase):
    def test_direct_json_contract(self):
        result=process_stage(event(),"simulated")
        self.assertEqual(set(result),{"ok","employee_id","stage","status","mode","result"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"],"complete")
        self.assertEqual(result["result"]["equipment_status"],"assigned")
    def test_same_correlation_is_deterministic(self):
        self.assertEqual(process_stage(event(),"simulated"),process_stage(event(),"simulated"))
    def test_policy_signoff(self):
        self.assertEqual(process_stage(event("policy_signoff"),"simulated")["result"]["policy_status"],"accepted")
    def test_manager_intro(self):
        self.assertEqual(process_stage(event("manager_intro"),"simulated")["result"]["invitation_status"],"created")
    def test_document_collection_rejected(self):
        with self.assertRaisesRegex(ValueError,"does not process"):
            process_stage(event("document_collection"),"simulated")
    def test_action_required(self):
        with self.assertRaisesRegex(ValueError,"action must be"):
            process_stage(event(action="wrong"),"simulated")
    def test_invalid_employee(self):
        with self.assertRaises(ValueError):
            process_stage(event(employee_id=" "),"simulated")
    def test_correlation_required(self):
        with self.assertRaisesRegex(ValueError,"correlation_id"):
            process_stage(event(correlation_id=" "),"simulated")
    def test_mode_must_match_deployment(self):
        with self.assertRaisesRegex(ValueError,"does not match"):
            process_stage(event(mode="real"),"simulated")
    def test_real_mode_fails_closed(self):
        with self.assertRaises(NotImplementedError):
            process_stage(event(mode="real"),"real")
    @patch.dict(os.environ,{"MODE":"simulated"},clear=True)
    def test_lambda_returns_direct_object(self):
        result=lambda_handler(event(),None)
        self.assertTrue(result["ok"])
        self.assertNotIn("statusCode",result)
    @patch.dict(os.environ,{},clear=True)
    def test_missing_mode_fails_closed(self):
        result=lambda_handler(event(),None)
        self.assertFalse(result["ok"])
        self.assertIn("MODE must be explicitly configured",result["error"])

if __name__=="__main__":
    unittest.main()
