"""Safe paginated backfill for employees who completed onboarding before email wiring."""
from __future__ import annotations

from typing import Any

try:
    from .completion import _all_stages_complete, send_completion_notification
except ImportError:  # Support direct Lambda module loading from CodeUri.
    from completion import _all_stages_complete, send_completion_notification


def _masked_email(value: Any) -> str | None:
    if not isinstance(value, str) or value.count("@") != 1:
        return None
    local, domain = value.split("@", 1)
    return (local[:1] + "***@" + domain) if local else "***@" + domain


def reconcile_completion_notifications(
    event: dict[str, Any],
    *,
    employees_table: Any,
    stages_table: Any,
    ses: Any | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Preview eligible employees by default; send only with explicit confirm_send=true.

    The caller repeats the action with next_cursor to process subsequent scan pages.
    A bounded page prevents one Lambda invocation from scanning an unbounded table.
    """
    confirm_send = event.get("confirm_send", False)
    if not isinstance(confirm_send, bool):
        raise ValueError("confirm_send must be a boolean")
    page_size = event.get("page_size", 25)
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= 100:
        raise ValueError("page_size must be an integer between 1 and 100")

    target_employee_id = event.get("employee_id")
    cursor = event.get("exclusive_start_key")
    if target_employee_id is not None:
        if not isinstance(target_employee_id, str) or not target_employee_id.strip():
            raise ValueError("employee_id must be a non-empty string")
        if cursor is not None:
            raise ValueError("exclusive_start_key cannot be combined with employee_id")
        target = employees_table.get_item(
            Key={"employee_id": target_employee_id.strip()},
            ConsistentRead=True,
        ).get("Item")
        response = {"Items": [target] if isinstance(target, dict) else []}
    else:
        scan_args: dict[str, Any] = {"Limit": page_size, "ConsistentRead": True}
        if cursor is not None:
            if not isinstance(cursor, dict) or not cursor:
                raise ValueError("exclusive_start_key must be a non-empty DynamoDB key object")
            scan_args["ExclusiveStartKey"] = cursor
        response = employees_table.scan(**scan_args)
    eligible: list[dict[str, str]] = []
    sent: list[str] = []
    skipped: dict[str, int] = {
        "already_sent": 0,
        "sending": 0,
        "incomplete": 0,
        "invalid_email": 0,
        "missing_employee_id": 0,
    }
    errors: list[dict[str, str]] = []

    for employee in response.get("Items", []):
        employee_id = employee.get("employee_id")
        if not isinstance(employee_id, str) or not employee_id.strip():
            skipped["missing_employee_id"] += 1
            continue

        status = employee.get("completion_email_status")
        if status == "sent":
            skipped["already_sent"] += 1
            continue
        if status == "sending":
            skipped["sending"] += 1
            continue

        email = employee.get("email")
        masked = _masked_email(email)
        if masked is None:
            skipped["invalid_email"] += 1
            continue

        missing = _all_stages_complete(stages_table, employee_id)
        if missing:
            skipped["incomplete"] += 1
            continue

        eligible.append({"employee_id": employee_id, "email": masked})
        if confirm_send:
            try:
                result = send_completion_notification(
                    {"employee_id": employee_id},
                    employees_table=employees_table,
                    stages_table=stages_table,
                    ses=ses,
                    now=now,
                )
                status = result.get("status")
                if status == "sent":
                    sent.append(employee_id)
                elif status == "already_sent":
                    skipped["already_sent"] += 1
                elif status == "sending":
                    skipped["sending"] += 1
                else:
                    errors.append({
                        "employee_id": employee_id,
                        "error": str(
                            result.get("error_code")
                            or result.get("reason")
                            or "COMPLETION_EMAIL_FAILED"
                        )[:80],
                    })
            except Exception as exc:  # Continue this page; report only safe error text.
                errors.append({
                    "employee_id": employee_id,
                    "error": type(exc).__name__,
                })

    return {
        "ok": not errors,
        "mode": "send" if confirm_send else "preview",
        "scanned": len(response.get("Items", [])),
        "eligible": eligible,
        "sent_employee_ids": sent,
        "skipped": skipped,
        "errors": errors,
        "next_cursor": response.get("LastEvaluatedKey"),
        "has_more": bool(response.get("LastEvaluatedKey")),
    }
