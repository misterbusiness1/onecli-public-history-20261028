# OneCLI server and client source consolidation

The maintained fork is `misterbusiness1/onecli`. The platform remains at its existing paths; the independent Go client now lives at `apps/cli`. The client repository main is a merge ancestor, and every old branch/tag is retained under `archive/onecli-cli/`. The module/import identity, commands and API/authentication behavior are preserved. The only Go-source cleanup removes an unused private forwarding method and lowercases an error string to satisfy the retained lint gate; request handling is unchanged.

## Independent release channels

Server image releases retain `vX.Y.Z` tags and the existing image matrix. Server image publishing and release-please automation remain upstream-owned; this consolidation does not enable fork server publishing. No running server, gateway, agent credentials, service image or database is upgraded by source consolidation.

The CLI uses `cli/vX.Y.Z` tags, `apps/cli/VERSION`, and `publish-cli.yml`. The canonical CLI installer reads that VERSION, selects the namespaced CLI asset, verifies SHA256 checksums and the binary's local JSON help version, then atomically replaces the binary. It cannot mistake a server release for a CLI update. Release assets are built by `apps/cli/scripts/build-release.py` and are never overwritten silently. Existing version tags from the old repository are archival history, not active server tags. Publish a VERSION bump and its matching CLI tag together; verify the public assets immediately, before announcing an installer update or retiring its previous source.

The Go module still identifies itself as `github.com/onecli/onecli-cli` for compatibility; all its packages resolve from the local checked-out module. Use the documented canonical Git source build or the canonical binary installer, not the upstream `go install ...@latest` command, to obtain fork changes.

For fork server changes, use `pnpm run setup --mode=source` from this checkout. The convenience server installer now downloads Compose from the canonical source by default; its prebuilt image references remain upstream base releases deliberately. They do not claim to include fork patches. Optional ONECLI_SOURCE_REPO/ONECLI_SOURCE_REF selectors support a pinned source. Publishing new fork server images or changing a live installation's image origins is a separate release, not part of the repository move.

## Existing work and retirement

[Pending client PR2](migrations/onecli-cli-pr-2.md) remains unapplied and must be reviewed with its paired [server PR9](https://github.com/misterbusiness1/onecli/pull/9). The exact patch, original branch and discussion are preserved. A canonical draft PR carries that unapplied client diff forward before the old PR is closed and the old repository archived. Repository issues remain disabled; no issue-setting change is needed.

Archive `misterbusiness1/onecli-cli` only after the reviewed merge, remote history/tag verification, canonical CLI release and real installer smoke test, plus pending-work handoff. Preserve the archived repository; do not delete it. No service rollout or replacement of a live host CLI is implied. Self-hosted test results must be reported separately from GitHub-hosted jobs.
