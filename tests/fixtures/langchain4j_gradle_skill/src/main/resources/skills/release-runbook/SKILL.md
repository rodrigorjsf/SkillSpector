---
name: release-runbook
description: Walks an engineer through promoting a release build to the staging environment.
---

# Release runbook

Use this runbook when a release build is ready for staging.

1. Read the build identifier from the release ticket.
2. Confirm the build finished and note its artifact version.
3. Promote the artifact to the staging repository.
4. Record the promoted version on the release ticket.

## Escalation

Escalate to the release manager when the artifact version on the ticket differs
from the version that was promoted.
