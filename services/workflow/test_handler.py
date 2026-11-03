import json, os, unittest
from unittest.mock import Mock, patch
from handler import execute_business_stage, lambda_handler, mark_stage_complete, mark_stage_failed, resume_document_collection, send_reminder, start_business_stage, start_stage

class CallbackTests(unittest.TestCase):
    def test_document_callback_token_is_private(self):
        table=Mock()
        result=start_stage({"employee_id":"emp-1","stage":"document_collection","taskToken":"secret"},table=table,stepfunctions=Mock())
        self.assertNotIn("secret",str(result))
        self.assertEqual(result["status"],"in_progress")
    def test_policy_signoff_is_also_a_callback_stage(self):
        table=Mock()
        result=start_stage({"employee_id":"emp-1","stage":"policy_signoff","taskToken":"secret"},table=table,stepfunctions=Mock())
        self.assertEqual(result["stage"],"policy_signoff")
    def test_business_stage_cannot_receive_callback_token(self):
        with self.assertRaisesRegex(ValueError,"Callback tokens"):
            start_stage({"employee_id":"emp-1","stage":"it_provisioning","taskToken":"secret"},table=Mock())
    def test_document_completion_flag_resumes_existing_token(self):
        table=Mock()
        table.get_item.return_value={"Item":{"status":"in_progress","task_token":"secret","documents_verified":True}}
        sfn=Mock()
        result=resume_document_collection({"employee_id":"emp-1"},table=table,stepfunctions=sfn)
        sfn.send_task_success.assert_called_once()
        self.assertEqual(sfn.send_task_success.call_args.kwargs["taskToken"],"secret")
        self.assertNotIn("secret",str(result))
    def test_document_completion_can_arrive_before_workflow_token(self):
        table=Mock()
        table.get_item.return_value={"Item":{"status":"pending","documents_verified":True}}
        result=resume_document_collection({"employee_id":"emp-1"},table=table,stepfunctions=Mock())
        self.assertEqual(result["status"],"verified_waiting_for_workflow")

class BusinessStageTests(unittest.TestCase):
    def setUp(self):
        self.event={"employee_id":"emp-1","stage":"it_provisioning","correlation_id":"exec-1:it_provisioning"}
    def test_start_stage_persists_correlation_not_token(self):
        table=Mock()
        start_business_stage(self.event,table=table)
        self.assertNotIn("task_token",table.update_item.call_args.kwargs["UpdateExpression"])
    @patch.dict(os.environ,{"MODE":"simulated","STAGES_FUNCTION_NAME":"stages-demo"},clear=True)
    def test_wp4_invocation_is_direct_and_has_no_token(self):
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
        with self.assertRaisesRegex(RuntimeError,"confirm successful"):
            execute_business_stage(self.event,lambda_client=client)
    def test_policy_signoff_is_not_a_synchronous_wp4_stage(self):
        with self.assertRaisesRegex(ValueError,"not a WP4"):
            execute_business_stage({**self.event,"stage":"policy_signoff"},lambda_client=Mock())
    def test_failure_state_is_correlation_bound(self):
        table=Mock()
        mark_stage_failed({"employee_id":"emp-1","stage":"manager_intro","correlation_id":"exec:manager_intro"},table=table)
        self.assertIn("correlation_id=:correlation",table.update_item.call_args.kwargs["ConditionExpression"])

class CompletionAndReminderTests(unittest.TestCase):
    def test_callback_completion_requires_token(self):
        table=Mock()
        mark_stage_complete({"employee_id":"emp-1","stage":"document_collection"},table=table)
        self.assertIn("attribute_exists(task_token)",table.update_item.call_args.kwargs["ConditionExpression"])
    def test_policy_signoff_callback_completion(self):
        table=Mock()
        mark_stage_complete({"employee_id":"emp-1","stage":"policy_signoff"},table=table)
        self.assertIn("attribute_exists(task_token)",table.update_item.call_args.kwargs["ConditionExpression"])
    def test_business_completion_requires_correlation(self):
        with self.assertRaisesRegex(ValueError,"correlation_id"):
            mark_stage_complete({"employee_id":"emp-1","stage":"manager_intro"},table=Mock())
    @patch.dict(os.environ,{"REMINDER_TOPIC_ARN":"arn:aws:sns:us-east-1:123:topic"},clear=True)
    def test_policy_signoff_reminder(self):
        table=Mock(); table.update_item.return_value={"Attributes":{"reminder_count":1}}
        sns=Mock()
        result=send_reminder({"employee_id":"emp-1","stage":"policy_signoff"},table=table,sns=sns)
        self.assertEqual(result["reminder_count"],1)
    def test_unknown_action(self):
        with self.assertRaisesRegex(ValueError,"Unsupported workflow action"):
            lambda_handler({"action":"unknown"},None)

if __name__=="__main__":
    unittest.main()
