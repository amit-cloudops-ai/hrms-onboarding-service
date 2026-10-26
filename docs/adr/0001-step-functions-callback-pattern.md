# ADR 0001: Step Functions with the callback (task token) pattern

**Status:** Accepted

**Context:** Stages depend on humans (uploading, signing) and can take days.

**Decision:** Each stage starts a Lambda with a task token and waits. The API returns the token to resume. A 24-hour timeout triggers a reminder and a loop back to waiting.

**Consequences:** Visible execution history, built-in timeouts, no polling code.
