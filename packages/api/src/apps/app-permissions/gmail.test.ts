import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { hostMatches, pathMatches } from "../../lib/path-match";
import { buildCatalogJson } from "./catalog-json";
import { gmailPermissions } from "./gmail";

const tool = gmailPermissions.groups
  .flatMap((group) => group.tools)
  .find((candidate) => candidate.id === "list_drafts")!;
const matches = (host: string, method: string, path: string) =>
  hostMatches(host, tool.hostPattern) &&
  method === tool.method &&
  [tool.pathPattern, ...(tool.aliasPatterns ?? [])].some((pattern) =>
    pathMatches(path, pattern),
  );

describe("Gmail draft read permission", () => {
  it.each([
    "/gmail/v1/users/me/drafts",
    "/gmail/v1/users/me/drafts?maxResults=100",
    "/gmail/v1/users/me/drafts/r123?format=raw",
    "/gmail/v1/users/info@example.test/drafts/r123?format=minimal",
  ])("allows GET %s", (path) => {
    expect(matches("gmail.googleapis.com", "GET", path)).toBe(true);
  });

  it.each([
    ["POST", "/gmail/v1/users/me/drafts"],
    ["PUT", "/gmail/v1/users/me/drafts/r123"],
    ["DELETE", "/gmail/v1/users/me/drafts/r123"],
    ["POST", "/gmail/v1/users/me/drafts/send"],
    ["POST", "/gmail/v1/users/me/messages/send"],
    ["GET", "/gmail/v1/users/me/drafts-other/r123"],
    ["GET", "/gmail/v1/users/me/messages/r123"],
  ])("rejects %s %s", (method, path) => {
    expect(matches("gmail.googleapis.com", method, path)).toBe(false);
  });

  it("rejects another host", () => {
    expect(
      matches("example.test", "GET", "/gmail/v1/users/me/drafts/r123"),
    ).toBe(false);
  });

  it("keeps API and generated gateway catalog in sync", () => {
    const generated = JSON.parse(
      readFileSync(
        new URL(
          "../../../../../apps/gateway/src/policy_engine/catalog.generated.json",
          import.meta.url,
        ),
        "utf8",
      ),
    );
    expect(generated.gmail).toEqual(buildCatalogJson([gmailPermissions]).gmail);
  });
});
