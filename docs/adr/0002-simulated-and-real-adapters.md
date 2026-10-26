# ADR 0002: Simulated and real adapters

**Status:** Accepted

**Context:** No real HR or IT system exists for this project, but real integrations make a stronger demo.

**Decision:** External systems sit behind adapter Lambdas with `MODE=simulated|real`. Secrets are stored in SSM Parameter Store.

**Consequences:** The demo cannot break on an outside API failure; swapping modes needs no workflow change.
