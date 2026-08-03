---
name: order-triage
description: Walks a support agent through triaging a customer order complaint.
---

# Order triage

Use this Skill when a customer disputes an order.

1. Read the order identifier from the customer's message.
2. Look up the order status and the product tier.
3. Compare the order date against the refund window for that tier.
4. Record the outcome on the support case.

## Escalation

Escalate to a human agent when the order falls outside its refund window and the
customer asks for an exception.
