# services/workflow

WP2 owns Step Functions orchestration, task-token lifecycle, reminders and canonical onboarding-stage status.

Document collection waits with lambda:invoke.waitForTaskToken. WP2 stores the token privately and resumes only through the trusted backend callback path. The three business stages are started by WP2, invoked synchronously through WP4, and marked complete by WP2 only after WP4 returns a valid direct JSON success object. WP4 never receives a task token and never writes canonical lifecycle fields.

STAGES_FUNCTION_NAME must name the deployed WP4 Lambda. MODE is required and must be simulated or real. Current WP4 supports simulated only; real mode fails closed.

Local tests: python -m unittest -v from this directory.
