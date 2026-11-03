from botocore.exceptions import ClientError, BotoCoreError
import json
import os
import unittest
from unittest.mock import MagicMock, patch

import handler


class TestDocumentHandler(unittest.TestCase):

    def setUp(self):
        self.employee_id = "employee-123"
        self.caller = {
            "sub": "cognito-user-123",
            "is_admin": False,
        }

    def s3_event(self):
        return {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "employee-123/id_proof/test.pdf"},
                },
            }]
        }

    @patch("handler.employees_table")
    @patch("handler.documents_table")
    def test_list_documents(self, mock_documents, mock_employees):
        mock_employees.get_item.return_value = {
            "Item": {
                "employee_id": self.employee_id,
                "cognito_sub": "cognito-user-123",
            }
        }

        mock_documents.get_item.return_value = {}

        event = {
            "action": "list_documents",
            "employee_id": self.employee_id,
            "caller": self.caller,
        }

        result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        self.assertIsInstance(result["body"], str)
        response_body = json.loads(result["body"])
        self.assertEqual(len(response_body["documents"]), 3)

        for document in response_body["documents"]:
            self.assertEqual(document["status"], "missing")

    def test_invalid_action(self):
        event = {
            "action": "unknown_action",
            "employee_id": self.employee_id,
            "caller": self.caller,
        }

        result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        self.assertEqual(
            json.loads(result["body"])["error"]["code"],
            "INVALID_REQUEST",
        )

    @patch("handler.employees_table")
    def test_employee_access_denied(self, mock_employees):
        mock_employees.get_item.return_value = {
            "Item": {
                "employee_id": self.employee_id,
                "cognito_sub": "different-user",
            }
        }

        event = {
            "action": "list_documents",
            "employee_id": self.employee_id,
            "caller": self.caller,
        }

        result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 403)
    @patch("handler.employees_table")
    def test_missing_employee_returns_not_found(self, mock_employees):
        mock_employees.get_item.return_value = {}

        event = {
            "action": "list_documents",
            "employee_id": self.employee_id,
            "caller": self.caller,
        }

        result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(
            json.loads(result["body"])["error"]["code"],
            "NOT_FOUND",
        )

    @patch("handler.s3_client")
    def test_valid_pdf_s3_upload(self, mock_s3):
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=b"%PDF-" + b"x" * 95)
            ),
            "ContentLength": 100,
            "ContentType": "application/pdf",
        }

        result = handler.validate_s3_object(
            bucket="test-bucket",
            object_key="employee-123/id_proof/test.pdf",
            expected_file_size=100,
            expected_content_type="application/pdf",
        )

        self.assertTrue(result)

    @patch("handler.s3_client")
    def test_invalid_s3_file_size(self, mock_s3):
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=b"%PDF-" + b"x" * 95)
            ),
            "ContentLength": 100,
            "ContentType": "application/pdf",
        }

        with self.assertRaises(ValueError):
            handler.validate_s3_object(
                bucket="test-bucket",
                object_key="employee-123/id_proof/test.pdf",
                expected_file_size=200,
                expected_content_type="application/pdf",
            )

    @patch("handler.s3_client")
    def test_invalid_s3_content_type(self, mock_s3):
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=b"%PDF-" + b"x" * 95)
            ),
            "ContentLength": 100,
            "ContentType": "image/jpeg",
        }

        with self.assertRaises(ValueError):
            handler.validate_s3_object(
                bucket="test-bucket",
                object_key="employee-123/id_proof/test.pdf",
                expected_file_size=100,
                expected_content_type="application/pdf",
            )

    @patch("handler.s3_client")
    def test_invalid_s3_signature(self, mock_s3):
        mock_s3.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=b"NOT-A-PDF" + b"x" * 91)
            ),
            "ContentLength": 100,
            "ContentType": "application/pdf",
        }

        with self.assertRaises(ValueError):
            handler.validate_s3_object(
                bucket="test-bucket",
                object_key="employee-123/id_proof/test.pdf",
                expected_file_size=100,
                expected_content_type="application/pdf",
            )
    @patch("handler.documents_table")
    def test_mark_document_verified(self, mock_table):
        result = handler.mark_document_verified(
            "employee-123",
            "id_proof",
            "employee-123/id_proof/test.pdf",
        )
        self.assertTrue(result)
        mock_table.update_item.assert_called_once()

    @patch("handler.documents_table")
    def test_mark_document_rejected(self, mock_table):
        result = handler.mark_document_rejected(
            "employee-123",
            "id_proof",
            "employee-123/id_proof/test.pdf",
        )
        self.assertTrue(result)
        mock_table.update_item.assert_called_once()

    @patch("handler.documents_table")
    def test_ignore_stale_verified_event(self, mock_table):
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "UpdateItem",
        )

        result = handler.mark_document_verified(
            "employee-123",
            "id_proof",
            "employee-123/id_proof/old.pdf",
        )
        self.assertFalse(result)

    @patch("handler.documents_table")
    def test_ignore_stale_rejected_event(self, mock_table):
        mock_table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "UpdateItem",
        )

        result = handler.mark_document_rejected(
            "employee-123",
            "id_proof",
            "employee-123/id_proof/old.pdf",
        )
        self.assertFalse(result)
    @patch("handler.validate_s3_object")
    @patch("handler.documents_table")
    @patch("handler.s3_client")
    def test_process_valid_upload(self, mock_s3, mock_table, mock_validate):
        mock_table.get_item.return_value = {
            "Item": {
                "s3_key": "employee-123/id_proof/test.pdf",
                "status": "missing",
                "file_size": 100,
                "content_type": "application/pdf",
            }
        }

        mock_validate.return_value = True

        event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": handler.DOCUMENTS_BUCKET_NAME or "test-bucket"},
                    "object": {"key": "employee-123/id_proof/test.pdf"},
                },
            }]
        }

        with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
            result = handler.process_s3_upload(event)

        self.assertTrue(result)
        mock_table.update_item.assert_called_once()

    @patch("handler.notify_hr_document_rejected")
    @patch("handler.mark_document_rejected", return_value=True)
    @patch("handler.validate_s3_object", side_effect=ValueError("Invalid file"))
    @patch("handler.documents_table")
    @patch("handler.s3_client")
    def test_process_invalid_upload(
        self, mock_s3, mock_table, mock_validate,
        mock_rejected, mock_notify
    ):
        mock_table.get_item.return_value = {
            "Item": {
                "s3_key": "employee-123/id_proof/test.pdf",
                "status": "missing",
                "file_size": 100,
                "content_type": "application/pdf",
            }
        }

        event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "employee-123/id_proof/test.pdf"},
                },
            }]
        }

        with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
            result = handler.lambda_handler(event, None)

        self.assertTrue(result)
        mock_s3.delete_object.assert_called_once()
        mock_notify.assert_called_once()

    @patch("handler.documents_table")
    @patch("handler.validate_s3_object")
    def test_ignore_old_upload_event(self, mock_validate, mock_table):
        mock_table.get_item.return_value = {
            "Item": {
                "s3_key": "employee-123/id_proof/new.pdf",
                "status": "missing",
                "file_size": 100,
                "content_type": "application/pdf",
            }
        }

        event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "employee-123/id_proof/old.pdf"},
                },
            }]
        }

        with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
            result = handler.lambda_handler(event, None)

        self.assertFalse(result)
        mock_validate.assert_not_called()

    @patch("handler.sns_client")
    def test_hr_notification(self, mock_sns):
        with patch.object(handler, "SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hr"):
            result = handler.notify_hr_document_rejected(
                "employee-123",
                "id_proof",
            )

        self.assertTrue(result)
        mock_sns.publish.assert_called_once()
    @patch("handler.process_s3_upload", return_value=True)
    def test_lambda_handler_routes_s3_event(self, mock_process):
        event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": "employee-123/id_proof/test.pdf"},
                },
            }]
        }

        result = handler.lambda_handler(event, None)

        self.assertTrue(result)
        mock_process.assert_called_once_with(event)

    def test_s3_unexpected_processing_failure_propagates(self):
        with patch(
            "handler.process_s3_upload",
            side_effect=RuntimeError("unexpected processing failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "unexpected processing failure",
            ):
                handler.lambda_handler(self.s3_event(), None)

    def test_s3_dynamodb_read_failure_propagates(self):
        error = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
            "GetItem",
        )

        with patch("handler.documents_table") as mock_table:
            mock_table.get_item.side_effect = error
            with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
                with self.assertRaises(ClientError):
                    handler.lambda_handler(self.s3_event(), None)

    def test_s3_object_read_failure_propagates(self):
        with patch("handler.documents_table") as mock_table:
            mock_table.get_item.return_value = {
                "Item": {
                    "s3_key": "employee-123/id_proof/test.pdf",
                    "status": "missing",
                    "file_size": 100,
                    "content_type": "application/pdf",
                }
            }
            with patch("handler.s3_client") as mock_s3:
                mock_s3.get_object.side_effect = ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
                    "GetObject",
                )
                with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
                    with self.assertRaises(ClientError):
                        handler.lambda_handler(self.s3_event(), None)

    def test_s3_status_write_failure_propagates(self):
        with patch("handler.documents_table") as mock_table:
            mock_table.get_item.return_value = {
                "Item": {
                    "s3_key": "employee-123/id_proof/test.pdf",
                    "status": "missing",
                    "file_size": 100,
                    "content_type": "application/pdf",
                }
            }
            mock_table.update_item.side_effect = ClientError(
                {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
                "UpdateItem",
            )
            with patch("handler.validate_s3_object", return_value=True):
                with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
                    with self.assertRaises(ClientError):
                        handler.lambda_handler(self.s3_event(), None)

    def test_s3_rejected_object_delete_failure_propagates(self):
        with patch("handler.documents_table") as mock_table:
            mock_table.get_item.return_value = {
                "Item": {
                    "s3_key": "employee-123/id_proof/test.pdf",
                    "status": "missing",
                    "file_size": 100,
                    "content_type": "application/pdf",
                }
            }
            with patch("handler.s3_client") as mock_s3:
                mock_s3.delete_object.side_effect = ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
                    "DeleteObject",
                )
                with patch(
                    "handler.validate_s3_object",
                    side_effect=ValueError("Invalid file"),
                ):
                    with patch(
                        "handler.notify_hr_document_rejected",
                        return_value=True,
                    ):
                        with patch.object(
                            handler,
                            "DOCUMENTS_BUCKET_NAME",
                            "test-bucket",
                        ):
                            with self.assertRaises(ClientError):
                                handler.lambda_handler(self.s3_event(), None)

    def test_s3_sns_publish_failure_propagates(self):
        with patch("handler.documents_table") as mock_table:
            mock_table.get_item.return_value = {
                "Item": {
                    "s3_key": "employee-123/id_proof/test.pdf",
                    "status": "missing",
                    "file_size": 100,
                    "content_type": "application/pdf",
                }
            }
            with patch("handler.s3_client"):
                with patch(
                    "handler.validate_s3_object",
                    side_effect=ValueError("Invalid file"),
                ):
                    with patch("handler.sns_client") as mock_sns:
                        mock_sns.publish.side_effect = ClientError(
                            {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
                            "Publish",
                        )
                        with patch.object(
                            handler,
                            "DOCUMENTS_BUCKET_NAME",
                            "test-bucket",
                        ):
                            with patch.object(
                                handler,
                                "SNS_TOPIC_ARN",
                                "arn:aws:sns:us-east-1:123456789012:hr",
                            ):
                                with self.assertRaises(ClientError):
                                    handler.lambda_handler(self.s3_event(), None)

    def test_internal_request_failure_keeps_api_error_response(self):
        event = {
            "action": "create_upload_url",
            "employee_id": self.employee_id,
            "caller": self.caller,
            "document": {
                "document_type": "id_proof",
                "content_type": "application/pdf",
                "file_size": 100,
            },
        }

        with patch("handler.validate_employee_access", return_value=True):
            with patch(
                "handler.create_upload_url",
                side_effect=ClientError(
                    {"Error": {"Code": "ServiceUnavailable", "Message": "retry"}},
                    "PutItem",
                ),
            ):
                result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 502)
        self.assertEqual(
            json.loads(result["body"])["error"]["code"],
            "DOWNSTREAM_ERROR",
        )

    @patch("handler.s3_client")
    def test_s3_content_length_mismatch_is_rejected_before_read(self, mock_s3):
        body = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": body,
            "ContentLength": 99,
            "ContentType": "application/pdf",
        }

        with self.assertRaises(ValueError):
            handler.validate_s3_object(
                bucket="test-bucket",
                object_key="employee-123/id_proof/test.pdf",
                expected_file_size=100,
                expected_content_type="application/pdf",
            )

        body.read.assert_not_called()

    @patch("handler.s3_client")
    def test_oversized_s3_content_is_rejected_before_read(self, mock_s3):
        body = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": body,
            "ContentLength": handler.MAX_FILE_SIZE + 1,
            "ContentType": "application/pdf",
        }

        with self.assertRaises(ValueError):
            handler.validate_s3_object(
                bucket="test-bucket",
                object_key="employee-123/id_proof/test.pdf",
                expected_file_size=handler.MAX_FILE_SIZE + 1,
                expected_content_type="application/pdf",
            )

        body.read.assert_not_called()

    @patch("handler.sns_client")
    def test_hr_notification_prefers_hr_notification_topic_env(self, mock_sns):
        expected_topic_arn = "arn:aws:sns:us-east-1:123456789012:hr-primary"

        with patch.dict(
            os.environ,
            {"HR_NOTIFICATION_TOPIC_ARN": expected_topic_arn},
        ), patch.object(handler, "SNS_TOPIC_ARN", "legacy-topic-arn"):
            result = handler.notify_hr_document_rejected(
                "employee-123",
                "id_proof",
            )

        self.assertTrue(result)
        self.assertEqual(
            mock_sns.publish.call_args.kwargs["TopicArn"],
            expected_topic_arn,
        )

    @patch("handler.sns_client")
    def test_hr_notification_retains_legacy_topic_fallback(self, mock_sns):
        expected_topic_arn = "arn:aws:sns:us-east-1:123456789012:hr-legacy"

        with patch.dict(
            os.environ,
            {"HR_NOTIFICATION_TOPIC_ARN": ""},
        ), patch.object(handler, "SNS_TOPIC_ARN", expected_topic_arn):
            result = handler.notify_hr_document_rejected(
                "employee-123",
                "id_proof",
            )

        self.assertTrue(result)
        self.assertEqual(
            mock_sns.publish.call_args.kwargs["TopicArn"],
            expected_topic_arn,
        )
    @patch("handler.s3_client")
    @patch("handler.documents_table")
    def test_create_upload_url_success(self, mock_table, mock_s3):
        mock_s3.generate_presigned_url.return_value = "https://test-upload-url"

        document = {
            "document_type": "id_proof",
            "content_type": "application/pdf",
            "file_size": 1024,
        }

        with patch.object(handler, "EMPLOYEES_TABLE_NAME", "employees"), \
             patch.object(handler, "DOCUMENTS_TABLE_NAME", "documents"), \
             patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):

            result = handler.create_upload_url(self.employee_id, document)

        self.assertEqual(result["statusCode"], 201)
        self.assertEqual(result["headers"]["Content-Type"], "application/json")
        response_body = json.loads(result["body"])
        self.assertEqual(response_body["upload_url"], "https://test-upload-url")
        self.assertEqual(response_body["expires_in_seconds"], 300)
        mock_table.put_item.assert_called_once()
        mock_s3.generate_presigned_url.assert_called_once()

    @patch("handler.documents_table")
    def test_verified_document_cannot_be_overwritten(self, mock_table):
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}},
            "PutItem",
        )

        document = {
            "document_type": "id_proof",
            "content_type": "application/pdf",
            "file_size": 1024,
        }

        with patch.object(handler, "EMPLOYEES_TABLE_NAME", "employees"), \
             patch.object(handler, "DOCUMENTS_TABLE_NAME", "documents"), \
             patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):

            result = handler.create_upload_url(self.employee_id, document)

        self.assertEqual(result["statusCode"], 409)
        self.assertEqual(
            json.loads(result["body"])["error"]["code"],
            "DOCUMENT_ALREADY_VERIFIED",
        )

    @patch("handler.s3_client")
    @patch("handler.documents_table")
    def test_upload_url_failure_cleans_metadata(self, mock_table, mock_s3):
        mock_s3.generate_presigned_url.side_effect = BotoCoreError(
            error_msg="URL generation failed"
        )

        document = {
            "document_type": "id_proof",
            "content_type": "application/pdf",
            "file_size": 1024,
        }

        with patch.object(handler, "EMPLOYEES_TABLE_NAME", "employees"), \
             patch.object(handler, "DOCUMENTS_TABLE_NAME", "documents"), \
             patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):

            with self.assertRaises(BotoCoreError):
                handler.create_upload_url(self.employee_id, document)

        mock_table.put_item.assert_called_once()
        mock_table.delete_item.assert_called_once()

    @patch("handler.process_single_s3_upload", side_effect=[True, True])
    def test_processes_every_s3_record_in_batch(self, mock_process):
        event = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "employee-123/id_proof/one.pdf"},
                    },
                },
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "employee-123/degree_certificate/two.pdf"},
                    },
                },
            ]
        }

        result = handler.process_s3_upload(event)

        self.assertTrue(result)
        self.assertEqual(mock_process.call_count, 2)


    @patch("handler.notify_hr_document_rejected")
    @patch("handler.s3_client")
    @patch("handler.documents_table")
    def test_retries_cleanup_and_notification_for_rejected_record(
        self, mock_table, mock_s3, mock_notify
    ):
        object_key = "employee-123/id_proof/test.pdf"
        mock_table.get_item.return_value = {
            "Item": {
                "s3_key": object_key,
                "status": "rejected",
            }
        }
        event = {
            "Records": [{
                "eventSource": "aws:s3",
                "s3": {
                    "bucket": {"name": "test-bucket"},
                    "object": {"key": object_key},
                },
            }]
        }

        with patch.object(handler, "DOCUMENTS_BUCKET_NAME", "test-bucket"):
            result = handler.process_s3_upload(event)

        self.assertTrue(result)
        mock_s3.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key=object_key,
        )
        mock_notify.assert_called_once_with("employee-123", "id_proof")


class TestLegacyS3BatchHandling(unittest.TestCase):
    def test_extractor_requires_explicit_record_for_multi_record_event(self):
        event = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "employee-123/id_proof/one.pdf"},
                    },
                },
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "employee-123/degree_certificate/two.pdf"},
                    },
                },
            ]
        }

        with self.assertRaisesRegex(ValueError, "explicit record"):
            handler.extract_s3_upload_details(event)

    @patch("handler.process_single_s3_upload", side_effect=[
        ValueError("malformed S3 record"),
        True,
    ])
    def test_batch_continues_after_bad_record_then_surfaces_failure(self, mock_process):
        event = {
            "Records": [
                {"eventSource": "aws:s3", "s3": {}},
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": "test-bucket"},
                        "object": {"key": "employee-123/degree_certificate/two.pdf"},
                    },
                },
            ]
        }

        with self.assertRaisesRegex(RuntimeError, "record\(s\): 0"):
            handler.process_s3_upload(event)

        self.assertEqual(mock_process.call_count, 2)


if __name__ == "__main__":
    unittest.main()

class TestEventBridgeS3Events(unittest.TestCase):
    def test_extracts_eventbridge_bucket_and_literal_key(self):
        event = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "employee-123/id_proof/file+name.pdf"},
            },
        }
        self.assertEqual(
            handler.extract_s3_upload_details(event),
            ("test-bucket", "employee-123/id_proof/file+name.pdf"),
        )

    def test_lambda_routes_eventbridge_object_created_event(self):
        event = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {
                "bucket": {"name": "test-bucket"},
                "object": {"key": "employee-123/id_proof/test.pdf"},
            },
        }
        with patch("handler.process_s3_upload", return_value=True) as process:
            self.assertTrue(handler.lambda_handler(event, None))
        process.assert_called_once_with(event)

    def test_rejects_incomplete_eventbridge_detail(self):
        event = {
            "source": "aws.s3",
            "detail-type": "Object Created",
            "detail": {"bucket": {"name": "test-bucket"}, "object": {}},
        }
        with self.assertRaisesRegex(ValueError, "Missing S3 bucket or object key"):
            handler.extract_s3_upload_details(event)


