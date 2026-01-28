# Security Guarantees and Threat Model

## Guarantees
- **No WRITE executes without approval**: WRITE actions require a valid approval
  token unless explicitly listed in `safe_writes_without_confirm`.
- **Receipts are privacy-preserving**: receipts never store raw args or content,
  only HMAC fingerprints and minimal metadata.
- **Tool access is adapter-only**: the control layer executes tools exclusively
  via registered adapters (no direct bypass in mocks).

## Threat Model Assumptions
- **Correct tool metadata**: ToolSpec action types (READ/WRITE) and scopes are
  accurate for the adapter’s behavior.
- **Trusted policy configuration**: Profiles are authored by trusted operators
  and are not user-controlled.
- **Secret handling**: `GATEWAY_SECRET` is protected and rotated for production.
- **Honest adapters**: Adapters respect scope inputs and do not leak data beyond
  requested scopes.
