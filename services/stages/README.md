# services/stages

WP4 is a synchronous business adapter for IT provisioning, policy sign-off and manager introduction.

WP2 invokes execute_stage synchronously with employee_id, stage, deployment-controlled mode, and stable correlation_id. WP4 returns a direct JSON object. It does not receive Step Functions task tokens and does not write canonical lifecycle fields to hrms-dev-onboarding-stages.

MODE is required at deployment and must be simulated or real. Current real-provider adapters are not implemented; real mode fails closed. Use simulated mode for the mentor demonstration.

Local test: python -m unittest services.stages.test_stages -v from the repository root.
