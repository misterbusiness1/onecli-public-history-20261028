OXFA worker credential boundary — isolated staging qualification

Status: PARTIAL. Do not call the email system fully fixed or production-ready.
The updated isolated staging image is healthy. Host, gateway, worker, and
cached-tunnel authentication qualification passed. Production is unchanged.

The original issue was reproduced in the live shared agent runtime: a UID 1000
process could select --agent default and obtain the same credential-bearing
proxy settings as the host operator. A CLI wrapper rule cannot close this path.

This staging candidate uses four boundaries:
1. OneCLI server based on e0ca80e, with cached-tunnel reauthentication: agent tokens are bound to their own configuration;
   anonymous production management and agent-token management access fail closed.
2. Native CLI 106ca2b: explicit assigned-token authentication, no invalid-token
   fallback to administrator login, no management key in the child environment.
3. Real Docker workers: separate PID namespaces, network=none, read-only root,
   no Linux capabilities, no-new-privileges, own token only, no shared admin home.
4. Fixed Unix-socket transports to the isolated API/gateway. Scoped firewall
   rules prevent the staged gateway from forwarding to live host services.

This is an isolated runtime qualification harness, not a completed migration of
Paperclip adapters. The workers execute diagnostic native CLI commands, not real
model heartbeats. The fixture database has zero provider connections. No live
OAuth credentials, customer email, real owner passkeys, or production databases
are copied. Actual adapter/client rollout and credential rotation remain required
before the live bypass can be considered closed.

Observed results:
- Full updated OneCLI server image built and staged successfully.
- Cached-auth regression failed before the fix. After the fix: 529 gateway unit
  tests passed, plus the explicitly run PostgreSQL token/scope regression.
- Post-upgrade checks: 46 worker, 16 host, and 6 gateway checks passed.
- Both staged workers passed all 23 checks in qualify-worker.py (46 total).
- Assigned access succeeds; native/default and direct-API identity overrides,
  missing/invalid token fallback, foreign scope, and management routes are denied.
- Worker file, capability, direct network, and environment restrictions passed.
- Six gateway checks passed: assigned/invalid/revoked/replacement credentials,
  a positive host listener control, and blocked indirect host connectivity.
- Sixteen host checks passed, including token rotation and distinct PID namespaces.
- All 46 worker checks passed again after fixture credential replacement.
- Two local relay regression tests passed.

Outstanding checks:
- Review actual adapter integration and preserve existing deployment overlays.
- Complete actual owner enrollment, coordinated client rollout, and release CI.

Server state (do not provision twice or replace private state):
  /home/ubuntu/oxfa-email-repair-20261026/runtime-isolation
  API source: /home/ubuntu/oxfa-email-repair-20261026/onecli-isolation
  Containers: oxfa-boundary-db, oxfa-boundary-api,
              oxfa-boundary-worker-a, oxfa-boundary-worker-b
  Internal network: oxfa-boundary-backend
  API address at provisioning: 192.168.192.3 (read current Docker metadata)
  Images: onecli-owner-isolation:cached-auth-20261026, oxfa-boundary-worker:106ca2b
  API image ID: sha256:41a0b454fa807f58e2070645d5e7e0332fa399883fd63e2580da6339a8a12fe6
  Previous API container is stopped and retained for rollback.
  Results: worker-results.json, host-results.json, gateway-results.json (server only)
  Private fixture state: private/ (NEVER commit or copy into a worker wholesale)
  Firewall ownership: private/firewall.json, OXFA_BOUNDARY chain scoped to API IP

stage.py provisions a NEW synthetic environment and refuses existing state.
ONECLI_STAGING_IMAGE selects the image; the manifest records its immutable ID.
upgrade-stage.py preserves the existing fixed IP and private data volume, and
rolls back automatically if the replacement API does not become healthy.
An initial health-check failure was corrected: Docker's internal network does
not publish the requested host ports, so the host relay now uses the fixed
staging container IP. The empty fixture was resumed once after verifying that
its agents table contained zero rows. It must not be reseeded now.

No production sender, grants, operator credentials, or adapter configurations
were changed. Do not remove production access or rotate shared credentials
without a qualified coordinated rollout and consumer inventory.

Review limitation: revalidation applies to subsequent HTTP requests, not
cancellation of already dispatched requests or already upgraded WebSocket streams.
Production promotion remains blocked by actual Paperclip adapter isolation,
owner enrollment on a separate hostname, client rollout, and complete CI checks.
