---
name: ops-runbook
description: Walks an operator through triaging a production alert for the billing service.
---

# Ops runbook

Use this runbook when a billing-service alert fires.

1. Read the alert summary and note the affected region.
2. Check the service health dashboard for the same region.
3. If error rate is above one percent, open an incident ticket.
4. Record the ticket id in the incident channel.

## Escalation

Escalate to the on-call engineer when the error rate stays above one percent for
more than ten minutes.
