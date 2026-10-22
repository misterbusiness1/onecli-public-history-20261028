# Agent identity isolation candidate — 2026-10-22

This candidate is not deployed. Passing component tests are not a claim of complete worker isolation.

## Native credential boundary

`GET /v1/container-config` accepts an `aoc_` bearer only for the identity belonging to that token. Omitted selectors use the authenticated identity, not the default agent. A different agent identifier, project or organization is rejected. Deleted or revoked credentials fail closed. An agent bearer cannot authenticate a management route or inherit a local administrator session.

This candidate makes production containers select authenticated OAuth mode when a signing secret is configured, otherwise API-key-only mode. Unauthenticated local administration requires the explicit development opt-in `ONECLI_ALLOW_UNAUTHENTICATED_LOCAL=true`; it must never be present in this production rollout. The existing owner administration key remains an operator credential, not a worker credential.

The accompanying native CLI v2.11.0 patch accepts `ONECLI_AGENT_TOKEN` for `onecli run`. A supplied invalid or empty token fails closed, without reading the shared administrative login. The CLI also removes administrative API keys from an agent-scoped child environment. Owner administrative CLI commands retain their existing authentication path.

## Required rollout, in order

1. Qualify this server image and the patched native CLI in an isolated environment. Test anonymous and invalid credentials, another identity/project/organization, revoked tokens, valid assigned access and valid owner administration. Record immutable artifacts and independent review.
2. Establish a real worker boundary for every active adapter: separate PID visibility and a filesystem allowlist that exposes only its own workspace and required credentials. Verify with the real runtime; configuration labels alone do not prove isolation. Existing Paperclip filesystem sandbox support needs runtime tooling and adapter coverage qualification, especially OpenCode.
3. Ensure no worker inherits server database/authentication/encryption secrets or a management API key, including copied values in explicit adapter environments. Do not print values during these checks. Keep legitimate per-run Paperclip credentials and assigned model subscription authentication.
4. Provision one scoped OneCLI identity/token per active worker. Preserve company separation and each role's existing grants; do not widen permissions or use the privileged default as a fallback. Verify existing secret references bind to the intended OneCLI identity before reusing them.
5. Remove the shared administrative credential files and forced shared login home from worker visibility. Keep the host operator login outside worker mounts. Inventory consumers before rotating any shared management key; do not blind-rotate a key required by an unrelated service.
6. Deploy the authenticated server, native CLI and worker bindings together in a coordinated window. Canary legitimate read access and negative bypass cases for every adapter, then resume work. Do not change provider billing, Codex/Claude subscription profiles, production stock or email delivery for these tests.

## Mandatory negative canaries

Changing or unsetting `ONECLI_AGENT` cannot yield another identity. Supplying `--agent cto` with a different assigned token returns 403. Unsetting the agent token cannot discover an administrative credential or enter ambient local administration. Direct API calls and direct native-binary invocation obey the same restriction. A worker cannot read another worker's environment/credential files or the host operator credential. All adapters must pass; a shared same-user runtime without these boundaries remains unsafe.

## Qualification evidence

The API regression first failed twice because agent bearers inherited an ambient administrative session. The corrected middleware/authentication suites and real-PostgreSQL configuration proof pass (38 tests). The web API-key-session tests pass (2), and container auth-mode selection tests pass (4). API typechecking passes. Native CLI command/API tests pass, including forbidden identity selection and no administrative key in an agent child. The full Rust gateway suite passes (527 tests). Full image qualification, independent review and real worker isolation remain explicit release gates.

Do not roll back to unauthenticated production administration as an availability workaround. Preserve authenticated operator recovery access and hold affected worker execution if a qualified boundary cannot be maintained.
