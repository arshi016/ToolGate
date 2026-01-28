# Agent -> Control Layer -> Tool Adapters (1-page spec)

## Purpose
Define how the Agent requests tool actions, how the Control Layer enforces
policy and confirmation, and how Tool Adapters execute calls with minimal,
safe data access. The Control Layer is the policy gatekeeper; Tool Adapters are
thin translators to external APIs.

## Components and flow
1. **Agent** prepares a tool request (tool, action, params, requested scope).
2. **Control Layer** normalizes the request, applies policy, and decides:
   allow, require confirmation, or block.
3. **Tool Adapter** executes allowed actions using approved scope, and returns
   results to the Control Layer.
4. **Control Layer** emits a receipt for every decision (allowed/confirmed/
   blocked) and returns the normalized response to the Agent.

## Definitions
- **READ**: data retrieval with no external side effects. Examples: list
  messages, fetch metadata, search, free/busy lookup.
- **WRITE**: any action that changes external state or triggers outbound
  effects. Examples: create/update/delete/move/share, send, invite, permission
  changes, or create drafts (drafts are still WRITE but may be safe).

## Policy rules (summary)
- **Default**: all WRITE actions require confirmation unless explicitly listed
  in `safe_writes_without_confirm`.
- **Risky WRITE rules (always confirm)**:
  - Sends/outbound communications (email.send, sms.send, invites).
  - Deletions, irreversible edits, or bulk updates.
  - Permission or sharing changes.
  - Payments, purchases, or account/security changes.
  - Exports or data exfiltration actions.
- **READ breadth rules**:
  - If `always_confirm_reads_if_broad` is true and the requested read is
    "broad", require confirmation.
  - A read is "broad" if its date range exceeds
    `broad_read_range_days_threshold` or if the query includes any
    `broad_read_keywords`.
- **Least-data scopes**:
  - If no scope is provided, use `read_default_scope`.
  - If a broader scope is requested, treat it as "broad" and apply confirmation
    rules.

## Receipt fields (returned for every decision)
- `receipt_id`, `timestamp`, `actor` (agent/user id)
- `profile` (policy profile name)
- `tool`, `action`, `read_write`
- `requested_scope`, `applied_scope`
- `confirmation_required`, `confirmation_obtained`
- `decision` (allowed | needs_confirmation | blocked)
- `policy_reason` (human-readable)
- `request_hash` (redacted input fingerprint)
- `result_summary` (redacted output summary)
- `error_code` / `error_message` (if blocked or failed)

## Blocked error behavior
When blocked, the Control Layer:
- **Does not call** the Tool Adapter.
- Returns a structured error with a stable code
  (e.g., `BLOCKED_BY_POLICY`) and a reason string.
- Provides a minimal remediation hint (e.g., "narrow date range").
- Logs the decision for audit with the same receipt fields.

## Non-goals / assumptions
- Not a UI spec; confirmation UX is handled elsewhere.
- Not responsible for authentication or identity proofing.
- Assumes Tool Adapters declare action metadata (READ/WRITE and scopes).
- Does not guarantee prevention of mis-labeled tool actions.
- Does not define tool-specific schemas beyond the adapter contract.
