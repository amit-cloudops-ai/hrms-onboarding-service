"""Offline WP3 tests; all AWS clients and tables are mocked."""
import json
import unittest
from io import BytesIO
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from services.documents import handler


class DocumentRequestTests(unittest.TestCase):
    def setUp(self):
        self.employees = Mock()
        self.employees.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "cognito_sub": "sub-1", "email": "newhire@example.com"
        }}
        self.documents = Mock()
        self.s3 = Mock()
        self.event = {
            "employee_id": "emp-1",
            "caller": {"sub": "sub-1", "email": "newhire@example.com", "is_admin": False},
            "document": {"document_type": "id_proof", "content_type": "application/pdf", "file_size": 1024},
        }

    def test_creates_short_lived_presigned_url_and_metadata(self):
        self.s3.generate_presigned_url.return_value = "https://signed.example/upload"
        with patch.dict(handler.os.environ, {"DOCUMENTS_BUCKET": "private-bucket", "UPLOAD_URL_TTL_SECONDS": "300"}):
            response = handler.create_upload_url(self.event, documents_table=self.documents,
                                                  employees_table=self.employees, s3=self.s3, now="now")
        self.assertEqual(response["statusCode"], 201)
        body = json.loads(response["body"])
        self.assertEqual(body["upload_url"], "https://signed.example/upload")
        self.assertEqual(body["required_headers"]["Content-Type"], "application/pdf")
        self.s3.generate_presigned_url.assert_called_once()
        args = self.s3.generate_presigned_url.call_args.kwargs
        self.assertEqual(args["ExpiresIn"], 300)
        self.assertEqual(args["Params"]["Bucket"], "private-bucket")
        item = self.documents.put_item.call_args.kwargs["Item"]
        self.assertEqual(item["status"], "missing")
        self.assertTrue(item["s3_key"].startswith("emp-1/id_proof/"))

    def test_rejects_wrong_employee_subject_before_presigning(self):
        self.event["caller"]["sub"] = "someone-else"
        response = handler.create_upload_url(self.event, documents_table=self.documents,
                                              employees_table=self.employees, s3=self.s3)
        self.assertEqual(response["statusCode"], 403)
        self.documents.put_item.assert_not_called()
        self.s3.generate_presigned_url.assert_not_called()

    def test_rejects_oversize_or_unsupported_file(self):
        self.event["document"]["file_size"] = handler.MAX_BYTES + 1
        response = handler.create_upload_url(self.event, documents_table=self.documents,
                                              employees_table=self.employees, s3=self.s3)
        self.assertEqual(response["statusCode"], 400)
        self.documents.put_item.assert_not_called()
        self.event["document"] = {"document_type": "id_proof", "content_type": "text/html", "file_size": 100}
        response = handler.create_upload_url(self.event, documents_table=self.documents,
                                              employees_table=self.employees, s3=self.s3)
        self.assertEqual(response["statusCode"], 400)

    def test_rejected_document_can_be_retried_with_a_fresh_object_key(self):
        old_key = "emp-1/id_proof/" + "b" * 32 + ".pdf"
        self.documents.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}}, "PutItem"
        )
        self.documents.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "doc_type": "id_proof", "s3_key": old_key, "status": "rejected",
        }}
        self.s3.generate_presigned_url.return_value = "https://signed.example/retry"
        with patch.dict(handler.os.environ, {"DOCUMENTS_BUCKET": "private-bucket", "UPLOAD_URL_TTL_SECONDS": "300"}):
            response = handler.create_upload_url(
                self.event, documents_table=self.documents,
                employees_table=self.employees, s3=self.s3, now="retry-time",
            )
        self.assertEqual(response["statusCode"], 201)
        update = self.documents.update_item.call_args.kwargs
        new_key = update["ExpressionAttributeValues"][":key"]
        self.assertNotEqual(new_key, old_key)
        self.assertEqual(update["ExpressionAttributeValues"][":status"], "missing")
        self.assertIn("upload_url", json.loads(response["body"]))
        self.s3.generate_presigned_url.assert_called_once()

    def test_conflicting_existing_document_returns_409(self):
        self.documents.put_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}}, "PutItem"
        )
        with patch.dict(handler.os.environ, {"DOCUMENTS_BUCKET": "private-bucket"}):
            response = handler.create_upload_url(self.event, documents_table=self.documents,
                                                  employees_table=self.employees, s3=self.s3)
        self.assertEqual(response["statusCode"], 409)
        self.s3.generate_presigned_url.assert_not_called()

    def test_lists_all_required_types_and_defaults_to_missing(self):
        self.documents.query.return_value = {"Items": [
            {"employee_id": "emp-1", "doc_type": "id_proof", "status": "verified"}
        ]}
        response = handler.list_documents(
            {"employee_id": "emp-1", "caller": {"sub": "sub-1"}},
            documents_table=self.documents, employees_table=self.employees,
        )
        self.assertEqual(response["statusCode"], 200)
        documents = json.loads(response["body"])["documents"]
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0]["status"], "verified")
        self.assertEqual(documents[1]["status"], "missing")
        self.assertEqual(documents[2]["status"], "missing")

    def test_pdf_signature_sniffing(self):
        self.assertTrue(handler._sniff("application/pdf", b"%PDF-1.7"))
        self.assertFalse(handler._sniff("application/pdf", b"<html>"))

    def test_valid_upload_is_verified_and_triggers_stage_when_all_docs_complete(self):
        key = "emp-1/id_proof/" + "a" * 32 + ".pdf"
        self.documents.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "doc_type": "id_proof", "s3_key": key,
            "status": "missing", "file_size": 10, "content_type": "application/pdf",
        }}
        self.documents.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified"},
            {"doc_type": "degree_certificate", "status": "verified"},
            {"doc_type": "signed_offer_letter", "status": "verified"},
        ]}
        self.s3.head_object.return_value = {"ContentLength": 10, "ContentType": "application/pdf"}
        body = Mock()
        body.read.return_value = b"%PDF-1.7abc"
        self.s3.get_object.return_value = {"Body": body}
        with patch.dict(handler.os.environ, {"STAGES_FUNCTION_NAME": "hrms-dev-stages"}), \
             patch.object(handler.boto3, "client") as client:
            result = handler.verify_uploaded_object("private-bucket", key, documents_table=self.documents,
                                                    s3=self.s3, now="now")
        self.assertEqual(result["status"], "verified")
        self.documents.update_item.assert_called_once()
        # File integrity validation alone must not advance onboarding; HR approval is a separate gate.
        client.return_value.invoke.assert_not_called()

    def test_invalid_magic_bytes_rejects_and_deletes_object(self):
        key = "emp-1/id_proof/" + "b" * 32 + ".pdf"
        self.documents.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "doc_type": "id_proof", "s3_key": key,
            "status": "missing", "file_size": 8, "content_type": "application/pdf",
        }}
        self.s3.head_object.return_value = {"ContentLength": 8, "ContentType": "application/pdf"}
        body = Mock()
        body.read.return_value = b"<html>!"
        self.s3.get_object.return_value = {"Body": body}
        sns = Mock()
        with patch.dict(handler.os.environ, {"HR_NOTIFICATION_TOPIC_ARN": "arn:topic"}):
            result = handler.verify_uploaded_object("private-bucket", key, documents_table=self.documents,
                                                    s3=self.s3, sns=sns, now="now")
        self.assertEqual(result["status"], "rejected")
        self.s3.delete_object.assert_called_once_with(Bucket="private-bucket", Key=key)
        sns.publish.assert_called_once()



class DocumentReviewTests(unittest.TestCase):
    def setUp(self):
        self.employees = Mock()
        self.employees.get_item.return_value = {"Item": {"employee_id": "emp-1", "cognito_sub": "sub-1"}}
        self.documents = Mock()
        self.documents.get_item.return_value = {"Item": {
            "employee_id": "emp-1", "doc_type": "id_proof",
            "s3_key": "emp-1/id_proof/" + "a" * 32 + ".pdf", "status": "verified",
        }}
        self.admin = {"sub": "hr-sub", "email": "hr@example.com", "is_admin": True}

    def test_review_url_is_admin_only_and_short_lived(self):
        s3 = Mock()
        s3.generate_presigned_url.return_value = "https://signed.example/read"
        with patch.dict(handler.os.environ, {"DOCUMENTS_BUCKET": "private-bucket"}):
            response = handler.create_review_url(
                {"employee_id": "emp-1", "document_type": "id_proof", "caller": self.admin},
                documents_table=self.documents, employees_table=self.employees, s3=s3,
            )
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(json.loads(response["body"])["review_url"], "https://signed.example/read")
        self.assertEqual(s3.generate_presigned_url.call_args.kwargs["ExpiresIn"], 300)
        denied = handler.create_review_url(
            {"employee_id": "emp-1", "document_type": "id_proof",
             "caller": {"sub": "sub-1", "is_admin": False}},
            documents_table=self.documents, employees_table=self.employees, s3=s3,
        )
        self.assertEqual(denied["statusCode"], 403)

    def test_rejection_requires_reason(self):
        response = handler.review_document(
            {"employee_id": "emp-1", "document_type": "id_proof", "decision": "rejected",
             "caller": self.admin},
            documents_table=self.documents, employees_table=self.employees,
        )
        self.assertEqual(response["statusCode"], 400)
        self.documents.update_item.assert_not_called()

    def test_approval_records_reviewer_and_completes_only_after_all_approved(self):
        self.documents.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified", "review_status": "approved"},
            {"doc_type": "degree_certificate", "status": "verified", "review_status": "approved"},
            {"doc_type": "signed_offer_letter", "status": "verified", "review_status": "approved"},
        ]}
        with patch.dict(handler.os.environ, {"STAGES_FUNCTION_NAME": "hrms-dev-stages"}), \
             patch.object(handler.boto3, "client") as client:
            client.return_value.invoke.return_value = {"Payload": BytesIO(b'{"statusCode":202,"body":"{}"}')}
            response = handler.review_document(
                {"employee_id": "emp-1", "document_type": "id_proof", "decision": "approved",
                 "caller": self.admin},
                documents_table=self.documents, employees_table=self.employees, now="review-time",
            )
        self.assertEqual(response["statusCode"], 200)
        values = self.documents.update_item.call_args.kwargs["ExpressionAttributeValues"]
        self.assertEqual(values[":reviewer"], "hr@example.com")
        self.assertEqual(values[":decision"], "approved")
        client.return_value.invoke.assert_called_once()

    def test_approval_does_not_complete_until_every_document_is_approved(self):
        self.documents.query.return_value = {"Items": [
            {"doc_type": "id_proof", "status": "verified", "review_status": "approved"},
            {"doc_type": "degree_certificate", "status": "verified", "review_status": "pending"},
            {"doc_type": "signed_offer_letter", "status": "verified", "review_status": "pending"},
        ]}
        with patch.object(handler.boto3, "client") as client:
            response = handler.review_document(
                {"employee_id": "emp-1", "document_type": "id_proof", "decision": "approved",
                 "caller": self.admin},
                documents_table=self.documents, employees_table=self.employees, now="review-time",
            )
        self.assertEqual(response["statusCode"], 200)
        client.assert_not_called()

if __name__ == "__main__":
    unittest.main()
