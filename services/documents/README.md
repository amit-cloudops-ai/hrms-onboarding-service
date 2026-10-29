# WP3 — Document collection

## Implemented contract

The Lambda handler is `services.documents.handler.lambda_handler`. It is invoked by WP5 using synchronous Lambda invocation and also receives S3 `ObjectCreated` events.

### Adapter requests

- `{"action":"create_upload_url","employee_id":"<uuid>","caller":{"sub":"<cognito-sub>","is_admin":false},"document":{"document_type":"id_proof","content_type":"application/pdf","file_size":12345}}`
- `{"action":"list_documents","employee_id":"<uuid>","caller":{"sub":"<cognito-sub>","is_admin":false}}`

The caller is authorized against the canonical employee record using immutable Cognito `sub`. HR administrators can list statuses. The API's Lambda execution role is the only expected invoker; do not grant direct public invoke permissions to this function.

### Upload and verification

1. WP5 authenticates and authorizes the employee.
2. WP3 validates the exact document type, declared content type, and size (1 byte–5 MiB), creates a random object key, writes the initial metadata record, and returns a five-minute presigned PUT URL.
3. The browser uploads using the returned `Content-Type` header. The bucket is private, encrypted, versioned, and blocks public access.
4. S3 invokes WP3 after object creation. WP3 compares actual size and content type to the registered metadata and checks PDF/JPEG/PNG magic bytes.
5. Valid files become `verified`; invalid files become `rejected`, are deleted, and trigger an HR notification. When all three required documents are verified, WP3 asks WP4 to resume `document_collection`.

Required types: `id_proof`, `degree_certificate`, `signed_offer_letter`. Accepted content types: `application/pdf`, `image/jpeg`, `image/png`. Maximum size: 5 MiB.

## Deployment template

`template.yaml` creates the private S3 bucket, S3-triggered Lambda, SNS notification topic, and least-privilege IAM statements. It expects existing employee, document, and stage tables. Deploy WP4 first and pass its `StagesFunctionName` output as the `StagesFunctionName` parameter.

Set `UploadAllowedOrigin` to the exact deployed portal origin before deployment. The default is localhost for development. Subscribe only an authorized HR notification endpoint to the output topic.

## Offline tests

From the repository root:

```bash
python -m unittest services.documents.test_handler -v
sam validate --lint --template-file services/documents/template.yaml
```

No live AWS resources are created by the tests. A live integration test must verify browser CORS, presigned PUT, S3 event delivery, metadata validation, and notification subscription.
