"""DynamoDB access for onboarding stage records."""

import os
import boto3
from services.stages.stages import (
    WP4_STAGES,
    validate_employee_id,
    validate_stage,
    validate_status,
)


def get_stages_table():
    table_name = os.environ.get(
        "STAGES_TABLE",
        "hrms-dev-onboarding-stages"
    )
    region = os.environ.get("AWS_REGION", "us-east-1")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=region
    )

    return dynamodb.Table(table_name)


def save_stage_record(record, table=None):
    """Save a stage record using the documented DynamoDB keys."""
    if not isinstance(record, dict):
        raise ValueError("Stage record must be a dictionary")

    validated_record = dict(record)
    validated_record["employee_id"] = validate_employee_id(
        record.get("employee_id")
    )
    validated_record["stage"] = validate_stage(record.get("stage"))
    if validated_record["stage"] not in WP4_STAGES:
        raise ValueError("WP4 does not persist this stage")
    validated_record["status"] = validate_status(record.get("status"))

    if table is None:
        table = get_stages_table()

    table.put_item(
        Item=validated_record,
        ConditionExpression=(
            "attribute_not_exists(#status) OR #status <> :complete"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":complete": "complete"},
    )

    return validated_record