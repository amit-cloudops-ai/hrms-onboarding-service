"""Offline tests for WP5. No AWS calls or resources are created."""
import json
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from services.api import handler


def event(method, path, *, claims=None, body=None, path_params=None):
    return {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": claims or {"email": "employee@example.com", "sub": "cognito-sub-123"}}},
        },
        "pathParameters": path_params or {},
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


class ApiResponseTests(unittest.TestCase):
    def test_requires_authenticated_claims(self):
        response = handler.lambda_handler({"rawPath": "/employees", "requestContext": {"http": {"method": "GET"}}}, None)
        self.assertEqual(response["statusCode"], 401)

    def test_non_admin_cannot_list_employees(self):
        response = handler.lambda_handler(event("GET", "/employees"), None)
        self.assertEqual(response["statusCode"], 403)

    def test_employee_can_resolve_current_profile_by_immutable_subject(self):
        employees = Mock()
        employees.scan.return_value = {"Items": [{
            "employee_id": "emp-current",
            "full_name": "Test Employee",
            "email": "employee@example.com",
            "cognito_sub": "cognito-sub-123",
            "execution_arn": "private-execution-arn",
        }]}
        stages = Mock()
        stages.query.return_value = {"Items": []}
        with patch.object(handler, "_employees_table", return_value=employees), \
             patch.object(handler, "_stages_table", return_value=stages):
            response = handler.lambda_handler(event("GET", "/employees/me"), None)
        self.assertEqual(response["statusCode"], 200)
        payload = json.loads(response["body"])
        self.assertEqual(payload["employee"]["employee_id"], "emp-current")
        self.assertEqual(payload["progress"]["employee_id"], "emp-current")
        self.assertNotIn("cognito_sub", response["body"])
        self.assertNotIn("private-execution-arn", response["body"])
        employees.scan.assert_called_once()

    def test_current_employee_endpoint_returns_not_found_for_unlinked_cognito_subject(self):
        employees = Mock()
        employees.scan.return_value = {"Items": []}
        with patch.object(handler, "_employees_table", return_value=employees):
            response = handler.lambda_handler(event("GET", "/employees/me"), None)
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "EMPLOYEE_PROFILE_NOT_LINKED")

    def test_current_employee_endpoint_rejects_ambiguous_subject_linkage(self):
        employees = Mock()
        employees.scan.return_value = {"Items": [
            {"employee_id": "emp-1", "cognito_sub": "cognito-sub-123"},
            {"employee_id": "emp-2", "cognito_sub": "cognito-sub-123"},
        ]}
        with patch.object(handler, "_employees_table", return_value=employees):
            response = handler.lambda_handler(event("GET", "/employees/me"), None)
        self.assertEqual(response["statusCode"], 409)
        self.assertEqual(json.loads(response["body"])["error"]["code"], "EMPLOYEE_PROFILE_AMBIGUOUS")

    def test_admin_group_can_list_employees(self):
        table = Mock()
        table.scan.return_value = {"Items": []}
        claims = {"email": "hr@example.com", "cognito:groups": "[\"hr-admins\"]"}
        with patch.object(handler, "_employees_table", return_value=table):
            response = handler.lambda_handler(event("GET", "/employees", claims=claims), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"]), {"employees": []})

    def test_employee_can_read_own_profile_but_execution_arn_is_hidden(self):
        employee = {"employee_id": "emp-1", "email": "employee@example.com", "cognito_sub": "cognito-sub-123", "execution_arn": "secret-arn"}
        table = Mock()
        table.get_item.return_value = {"Item": employee.copy()}
        with patch.object(handler, "_employees_table", return_value=table):
            response = handler.lambda_handler(event("GET", "/employees/emp-1", path_params={"employee_id": "emp-1"}), None)
        self.assertEqual(response["statusCode"], 200)
        self.assertNotIn("execution_arn", json.loads(response["body"])["employee"])
        self.assertNotIn("cognito_sub", json.loads(response["body"])["employee"])

    def test_email_match_without_cognito_sub_does_not_grant_self_access(self):
        table = Mock()
        table.get_item.return_value = {
            "Item": {"employee_id": "emp-3", "email": "employee@example.com"}
        }
        with patch.object(handler, "_employees_table", return_value=table):
            response = handler.lambda_handler(
                event("GET", "/employees/emp-3", path_params={"employee_id": "emp-3"}),
                None,
            )
        self.assertEqual(response["statusCode"], 403)

    def test_employee_cannot_read_another_employee(self):
        table = Mock()
        table.get_item.return_value = {"Item": {"employee_id": "emp-2", "email": "other@example.com", "cognito_sub": "different-sub"}}
        with patch.object(handler, "_employees_table", return_value=table):
            response = handler.lambda_handler(event("GET", "/employees/emp-2", path_params={"employee_id": "emp-2"}), None)
        self.assertEqual(response["statusCode"], 403)

    def test_other_employee_cannot_request_upload_url_or_sign_policy(self):
        employee_table = Mock()
        employee_table.get_item.return_value = {
            "Item": {
                "employee_id": "emp-other",
                "email": "employee@example.com",
                "cognito_sub": "different-subject",
            }
        }
        upload = event(
            "POST", "/employees/emp-other/documents/upload-url",
            body={"document_type": "id_proof"},
            path_params={"employee_id": "emp-other"},
        )
        sign = event(
            "POST", "/employees/emp-other/policies/sign",
            body={"policy_id": "acceptable-use"},
            path_params={"employee_id": "emp-other"},
        )
        with patch.object(handler, "_employees_table", return_value=employee_table), \
             patch.object(handler, "_invoke_service") as invoke:
            upload_response = handler.lambda_handler(upload, None)
            sign_response = handler.lambda_handler(sign, None)
        self.assertEqual(upload_response["statusCode"], 403)
        self.assertEqual(sign_response["statusCode"], 403)
        invoke.assert_not_called()

    def test_employee_list_does_not_leak_internal_identity_or_execution_fields(self):
        employees = Mock()
        employees.scan.return_value = {"Items": [{
            "employee_id": "emp-1",
            "email": "employee@example.com",
            "cognito_sub": "internal-sub",
            "execution_arn": "internal-execution-arn",
        }]}
        stages = Mock()
        stages.query.return_value = {"Items": []}
        claims = {"email": "hr@example.com", "cognito:groups": ["hr-admins"]}
        with patch.object(handler, "_employees_table", return_value=employees), \
             patch.object(handler, "_stages_table", return_value=stages):
            response = handler.lambda_handler(event("GET", "/employees", claims=claims), None)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        serialized = json.dumps(body)
        self.assertNotIn("internal-sub", serialized)
        self.assertNotIn("internal-execution-arn", serialized)

    def test_downstream_lambda_function_error_is_sanitized(self):
        payload = Mock()
        payload.read.return_value = b'{"error":"secret details"}'
        with patch.object(handler.boto3, "client") as client:
            client.return_value.invoke.return_value = {
                "FunctionError": "Unhandled",
                "Payload": payload,
            }
            response = handler._invoke_service("adapter-name", {"action": "list_documents"})
        self.assertEqual(response["statusCode"], 502)
        self.assertNotIn("secret details", response["body"])

    def test_admin_stage_completion_submits_server_side_callback(self):
        claims = {"email": "hr@example.com", "cognito:groups": ["hr-admins"]}
        req = event(
            "POST", "/employees/emp-1/stages/document_collection/complete",
            claims=claims,
            path_params={"employee_id": "emp-1", "stage": "document_collection"},
        )
        employees = Mock()
        employees.get_item.return_value = {"Item": {"employee_id": "emp-1"}}
        stages = Mock()
        with patch.object(handler, "_employees_table", return_value=employees), \
             patch.object(handler, "_stages_table", return_value=stages), \
             patch("services.workflow.callbacks.resume_stage", return_value={
                 "ok": True, "employee_id": "emp-1",
                 "stage": "document_collection", "status": "completion_submitted",
             }) as resume:
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 202)
        self.assertTrue(resume.call_args.kwargs["authorized"])
        self.assertNotIn("task_token", response["body"])

    def test_manager_intro_completion_is_routed_through_wp4(self):
        claims = {"email": "hr@example.com", "sub": "hr-sub", "cognito:groups": ["hr-admins"]}
        req = event(
            "POST", "/employees/emp-1/stages/manager_intro/complete",
            claims=claims,
            path_params={"employee_id": "emp-1", "stage": "manager_intro"},
        )
        employees = Mock()
        employees.get_item.return_value = {"Item": {"employee_id": "emp-1"}}
        with patch.object(handler, "_employees_table", return_value=employees), \
             patch.object(handler, "_invoke_service", return_value=handler._response(202, {"status": "completion_submitted"})) as invoke:
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 202)
        payload = invoke.call_args.args[1]
        self.assertEqual(payload["action"], "complete_stage")
        self.assertEqual(payload["source"], "hr_admin")
        self.assertTrue(payload["caller"]["is_admin"])
        self.assertEqual(payload["caller"]["sub"], "hr-sub")

    def test_non_admin_cannot_submit_stage_completion(self):
        req = event(
            "POST", "/employees/emp-1/stages/document_collection/complete",
            path_params={"employee_id": "emp-1", "stage": "document_collection"},
        )
        with patch("services.workflow.callbacks.resume_stage") as resume:
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 403)
        resume.assert_not_called()

    def test_malformed_json_is_400(self):
        req = event("POST", "/employees", claims={"email": "hr@example.com", "cognito:groups": ["hr-admins"]})
        req["body"] = "{"
        response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 400)

    def test_progress_includes_missing_stages_as_pending(self):
        table = Mock()
        table.query.return_value = {"Items": [{"employee_id": "emp-1", "stage": "document_collection", "status": "complete"}]}
        progress = handler.get_progress("emp-1", table=table)
        self.assertEqual(progress["completed_stages"], 1)
        self.assertEqual(progress["total_stages"], 4)
        self.assertEqual(progress["stages"][1]["status"], "pending")

    def test_missing_document_integration_fails_closed(self):
        with patch.dict(handler.os.environ, {"DOCUMENTS_FUNCTION_NAME": ""}):
            response = handler._invoke_service("", {"action": "list_documents"})
        self.assertEqual(response["statusCode"], 503)

    def test_create_employee_starts_workflow_and_hides_execution_arn(self):
        table = Mock()
        created = {
            "employee_id": "emp-1", "email": "employee@example.com",
            "status": "in_progress", "created_at": "now",
        }
        claims = {"email": "hr@example.com", "cognito:groups": ["hr-admins"]}
        req = event("POST", "/employees", claims=claims, body={"full_name": "Test"})
        with patch.dict(handler.os.environ, {"STATE_MACHINE_ARN": "arn:test:state-machine", "COGNITO_USER_POOL_ID": "pool-test"}), \
             patch.object(handler, "_employees_table", return_value=table), \
             patch.object(handler, "create_employee", return_value=created), \
             patch.object(handler, "_start_onboarding", return_value={**created, "execution_arn": "private-arn"}):
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 201)
        self.assertNotIn("execution_arn", json.loads(response["body"])["employee"])

    def test_create_employee_rejects_non_admin_before_identity_creation(self):
        req = event("POST", "/employees", body={"full_name": "Test"})
        with patch.object(handler, "create_employee") as create:
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 403)
        create.assert_not_called()

    def test_missing_workflow_configuration_does_not_create_identity(self):
        req = event("POST", "/employees", claims={"email": "hr@example.com", "cognito:groups": ["hr-admins"]}, body={"full_name": "Test"})
        with patch.dict(handler.os.environ, {"STATE_MACHINE_ARN": "", "COGNITO_USER_POOL_ID": "pool-test"}), \
             patch.object(handler, "create_employee") as create:
            response = handler.lambda_handler(req, None)
        self.assertEqual(response["statusCode"], 503)
        create.assert_not_called()

    def test_start_onboarding_persists_execution_arn(self):
        table = Mock()
        sfn = Mock()
        sfn.start_execution.return_value = {"executionArn": "arn:aws:states:us-east-1:123:execution:test:emp-1"}
        with patch.dict(handler.os.environ, {"STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123:stateMachine:test"}), \
             patch.object(handler.boto3, "client", return_value=sfn):
            result = handler._start_onboarding({"employee_id": "emp-1", "email": "employee@example.com"}, employees_table=table)
        self.assertEqual(result["execution_arn"], sfn.start_execution.return_value["executionArn"])
        table.update_item.assert_called_once()

    def test_start_onboarding_failure_attempts_both_cleanup_actions(self):
        table = Mock()
        sfn = Mock()
        sfn.start_execution.side_effect = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "StartExecution")
        cognito = Mock()
        with patch.dict(handler.os.environ, {"STATE_MACHINE_ARN": "arn:aws:states:us-east-1:123:stateMachine:test", "COGNITO_USER_POOL_ID": "pool-test"}), \
             patch.object(handler.boto3, "client", side_effect=[sfn, cognito]):
            with self.assertRaisesRegex(RuntimeError, "Could not start onboarding workflow"):
                handler._start_onboarding({"employee_id": "emp-1", "email": "employee@example.com"}, employees_table=table)
        cognito.admin_delete_user.assert_called_once()
        table.delete_item.assert_called_once_with(Key={"employee_id": "emp-1"})


if __name__ == "__main__":
    unittest.main()
