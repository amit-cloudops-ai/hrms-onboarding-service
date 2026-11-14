"""Core stage definitions and validation for HRMS onboarding."""
STAGES=("document_collection","it_provisioning","policy_signoff","manager_intro")
WP4_STAGES=("it_provisioning","manager_intro")
STATUSES=("pending","in_progress","complete","failed")
def validate_employee_id(employee_id):
    if not isinstance(employee_id,str) or not employee_id.strip(): raise ValueError("employee_id is required")
    return employee_id.strip()
def validate_stage(stage):
    if stage not in STAGES: raise ValueError(f"Unsupported stage: {stage}")
    return stage
def validate_status(status):
    if status not in STATUSES: raise ValueError(f"Unsupported status: {status}")
    return status
def build_stage_record(employee_id,stage,status="pending"):
    return {"employee_id":validate_employee_id(employee_id),"stage":validate_stage(stage),"status":validate_status(status),"reminder_count":0}
