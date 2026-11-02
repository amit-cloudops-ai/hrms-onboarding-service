import json
import os
import unittest
from unittest.mock import patch

from services.stages.handler import lambda_handler, process_stage
from services.stages.stages import STAGES, STATUSES, WP4_STAGES


def event(stage="it_provisioning", **overrides):
    value = {
        "action": "execute_stage",
        "employee_id": "EMP001",
        "stage": stage,
        "correlation_id": "exec-123-stage-" + stage,
    }
    value.update(overrides)
    return value


class TestStageDefinitions(unittest.TestCase):
    def test_all_stages_exist(self):
        self.assertEqual(len(STAGES), 4)

    def test_statuses(self):
        self.assertEqual(STATUSES, ("pending", "in_progress", "complete"))

    def test_wp4_only_owns_business_stages(self):
        self.assertEqual(
            WP4_STAGES,
            ("it_provisioning", "policy_signoff", "manager_intro"),
        )
        self.assertNotIn("document_collection", WP4_STAGES)


class TestWP4BusinessAdapter(unittest.TestCase):
    def test_it_provisioning_contract_response(self):
        result = process_stage(event())
        self.assertEqual(
            set(result),
            {"ok", "employee_id", "stage", "status", "mode", "result"},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["mode"], "simulated")
        self.assertEqual(result["result"]["equipment_status"], "assigned")
        self.assertEqual(result["result"]["account_status"], "created")

    def test_same_correlation_returns_same_simulated_result(self):
        first = process_stage(event())
        second = process_stage(event())
        self.assertEqual(first, second)

    def test_policy_signoff(self):
        result = process_stage(event("policy_signoff"))
        self.assertEqual(result["result"]["policy_status"], "accepted")

    def test_manager_intro(self):
        result = process_stage(event("manager_intro"))
        self.assertEqual(result["result"]["invitation_status"], "created")

    def test_document_collection_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not process"):
            process_stage(event("document_collection"))

    def test_action_required(self):
        with self.assertRaisesRegex(ValueError, "action must be"):
            process_stage(event(action="wrong"))

    def test_correlation_id_required(self):
        with self.assertRaisesRegex(ValueError, "correlation_id is required"):
            process_stage(event(correlation_id=" "))

    def test_employee_id_required(self):
        with self.assertRaises(ValueError):
            process_stage(event(employee_id=" "))

    def test_invalid_stage_rejected(self):
        with self.assertRaises(ValueError):
            process_stage(event("unknown"))

    def test_non_object_event_rejected(self):
        with self.assertRaises(ValueError):
            process_stage(None)

    def test_real_mode_fails_closed(self):
        with self.assertRaises(NotImplementedError):
            process_stage(event(), mode="real")

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            process_stage(event(), mode="other")

    @patch.dict(os.environ, {"MODE": "simulated"}, clear=False)
    def test_lambda_handler_uses_deployment_mode_and_contract(self):
        result = lambda_handler(event(), None)
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(json.loads(result["body"])["ok"], True)

    @patch.dict(os.environ, {"MODE": "real"}, clear=False)
    def test_lambda_handler_does_not_allow_event_to_override_mode(self):
        request = event(mode="simulated")
        result = lambda_handler(request, None)
        self.assertEqual(result["statusCode"], 501)
        self.assertFalse(json.loads(result["body"])["ok"])


if __name__ == "__main__":
    unittest.main()
