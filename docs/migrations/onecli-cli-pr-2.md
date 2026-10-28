# Pending CLI security work carried forward

Original PR: https://github.com/misterbusiness1/onecli-cli/pull/2

Head: `8f6b5ba20e2954d3e3a8cc90d08b268bed631fda`. Its branch is preserved as `archive/onecli-cli/branches/fix/oxfa-email-runtime-token` in this repository. The exact authored patch is `onecli-cli-pr-2.patch` beside this file; it remains unapplied to main CLI behavior.

Keep this change pending until its paired server authentication work, https://github.com/misterbusiness1/onecli/pull/9, and enforced managed-worker rollout are qualified. Consolidation does not approve or activate that security change. Continue its review in this repository; use the archived original PR for discussion and staging evidence. Apply the patch beneath `apps/cli` with a three-way merge and resolve against the current client, retaining its shipped run-context behavior. Re-run the native CLI/server boundary integration checks before considering release.
