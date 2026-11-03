import json
import os
import unittest
from unittest.mock import Mock, patch
from handler import execute_business_stage, lambda_handler, mark_stage_complete, mark_stage_failed, send_reminder, start_business_stage, start_stage

class StartDocumentStageTests(unittest.TestCase):
    def test_callback_token_is_private_and_only_for_documents(self):
        table=Mock()
        result=start_stage({"employee_id":"emp-1","stage":"document_collection","taskToken":"secret"},table=table)
        self.assertEqual(result["status"],"in_progress")
        self.assertNotIn("secret",str(result))
        with self.assertRaisesRegex(ValueError,"reserved for document_collection"):
            start_stage({"employee_id":"emp-1","stage":"it_provisioning","taskToken":"secret"},table=Mock())

class BusinessStageTests(unittest.TestCase):
    def setUp(self):
        self.event={"employee_id":"emp-1","stage":"it_provisioning","correlation_id":"exec-1:it_provisioning"}
    def test_start_business_stage_has_no_task_token(self):
        table=Mock()
        result=start_business_stage(self.event,table=table)
        self.assertNotIn("task_token",table.update_item.call_args.kwargs["UpdateExpression"])
        self.assertEqual(result["status"],"in_progress")
    @patch.dict(os.environ,{"MODE":"simulated","STAGES_FUNCTION_NAME":"stages-demo"},clear=True)
    def test_invokes_wp4_with_direct_contract_without_task_token(self):
        body={"ok":True,"employee_id":"emp-1","stage":"it_provisioning","status":"complete","mode":"simulated","result":{}}
        stream=Mock(); stream.read.return_value=json.dumps(body).encode()
        client=Mock(); client.invoke.return_value={"Payload":stream}
        result=execute_business_stage(self.event,lambda_client=client)
        sent=json.loads(client.invoke.call_args.kwargs["Payload"])
        self.assertEqual(sent["action"],"execute_stage")
        self.assertNotIn("taskToken",sent)
        self.assertEqual(result,body)
    @patch.dict(os.environ,{"MODE":"simulated","STAGES_FUNCTION_NAME":"stages-demo"},clear=True)
    def test_rejects_api_gateway_envelope(self):
        stream=Mock(); stream.read.return_value=json.dumps({"statusCode":200,"body":"{}"}).encode()
        client=Mock(); client.invoke.return_value={"Payload":stream}
        with self.assertRaisesRegex(RuntimeError,"did not confirm"):
            execute_business_stage(self.event,lambda_client=client)
    @patch.dict(os.environ,{"MODE":"simulated"},clear=True)
    def test_missing_stage_function_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"STAGES_FUNCTION_NAME"):
            execute_business_stage(self.event,lambda_client=Mock())
    @patch.dict(os.environ,{"STAGES_FUNCTION_NAME":"stages-demo"},clear=True)
    def test_missing_mode_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,"MODE"):
            execute_business_stage(self.event,lambda_client=Mock())
    def test_document_stage_not_sent_to_wp4(self):
        with self.assertRaisesRegex(ValueError,"not a WP4"):
            start_business_stage({**self.event,"stage":"document_collection"},table=Mock())

class CompletionTests(unittest.TestCase):
    def test_business_completion_bound_to_correlation(self):
        table=Mock()
        mark_stage_complete({"employee_id":"emp-1","stage":"it_provisioning","correlation_id":"exec-1:it_provisioning"},table=table)
        self.assertIn("correlation_id = :correlation_id",table.update_item.call_args.kwargs["ConditionExpression"])
    def test_document_completion_requires_token(self):
        table=Mock()
        mark_stage_complete({"employee_id":"emp-1","stage":"document_collection"},table=table)
        self.assertIn("attribute_exists(task_token)",table.update_item.call_args.kwargs["ConditionExpression"])
    def test_business_completion_requires_correlation(self):
        with self.assertRaisesRegex(ValueError,"requires correlation_id"):
            mark_stage_complete({"employee_id":"emp-1","stage":"policy_signoff"},table=Mock())
    def test_failure_state_is_correlation_bound(self):
        table=Mock()
        mark_stage_failed({"employee_id":"emp-1","stage":"manager_intro","correlation_id":"exec:manager_intro"},table=table)
        self.assertIn("correlation_id = :correlation_id",table.update_item.call_args.kwargs["ConditionExpression"])

class ReminderTests(unittest.TestCase):
    @patch.dict(os.environ,{"REMINDER_TOPIC_ARN":"arn:aws:sns:us-east-1:123:topic"},clear=True)
    def test_reminder(self):
        table=Mock(); table.update_item.return_value={"Attributes":{"reminder_count":1}}
        sns=Mock()
        result=send_reminder({"employee_id":"emp-1","stage":"document_collection"},table=table,sns=sns)
        self.assertEqual(result["reminder_count"],1)
        sns.publish.assert_called_once()
    def test_reminder_only_for_document_collection(self):
        with self.assertRaisesRegex(ValueError,"document_collection"):
            send_reminder({"employee_id":"emp-1","stage":"policy_signoff"},table=Mock(),sns=Mock())

class DispatcherTests(unittest.TestCase):
    def test_unknown_action(self):
        with self.assertRaisesRegex(ValueError,"Unsupported workflow action"):
            lambda_handler({"action":"unknown"},None)

if __name__=="__main__":
    unittest.main()
