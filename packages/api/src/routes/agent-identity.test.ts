import { beforeEach, describe, expect, it, vi } from "vitest";
import { Hono } from "hono";
import type { ApiEnv } from "../types";
const mocks = vi.hoisted(() => ({ find: vi.fn(), admin: vi.fn() }));
vi.mock("@onecli/db", () => ({ db: { agent: { findUnique: mocks.find } } }));
vi.mock("../middleware/auth", () => ({ authMiddleware: mocks.admin }));
import { agentIdentityRoutes } from "./agent-identity";
const TOKEN = "aoc_" + "1".repeat(64);
const identity = {
  id: "agent-a",
  identifier: "worker-a",
  projectId: "project-a",
  organizationId: "org-a",
};
const app = () =>
  new Hono<ApiEnv>().route("/v1/agent-identity", agentIdentityRoutes());
const request = (
  url = "/v1/agent-identity",
  authorization = `Bearer ${TOKEN}`,
  extra: Record<string, string> = {},
) =>
  app().request(url, {
    headers: { ...(authorization ? { authorization } : {}), ...extra },
  });
describe("assigned agent metadata only", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.find.mockResolvedValue({
      ...identity,
      accessToken: TOKEN,
      project: { organizationId: identity.organizationId },
      secretFixture: "never-return",
    });
    // Ambient admin authentication would succeed: the endpoint must never call it.
    mocks.admin.mockImplementation((c) => c.json({ administrative: true }));
  });
  it("returns only the canonical tuple without returning a token or configuration", async () => {
    const response = await request();
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(response.headers.get("vary")).toBe("Authorization");
    expect(await response.json()).toEqual(identity);
    expect(mocks.find).toHaveBeenCalledWith({
      where: { accessToken: TOKEN },
      select: {
        id: true,
        identifier: true,
        projectId: true,
        accessToken: true,
        project: { select: { organizationId: true } },
      },
    });
    expect(mocks.admin).not.toHaveBeenCalled();
  });
  it("accepts matching explicit selector, project and organization", async () => {
    const response = await request(
      "/v1/agent-identity?agent=worker-a",
      `Bearer ${TOKEN}`,
      {
        "x-project-id": "project-a",
        "x-organization-id": "org-a",
      },
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(identity);
  });
  for (const [label, bearer] of [
    ["missing", ""],
    ["owner key", "Bearer oc_owner"],
    ["basic", "Basic fixture"],
    ["malformed", "Bearer aoc_bad"],
    ["empty", "Bearer aoc_"],
    ["trailing words", `Bearer ${TOKEN} extra`],
    ["uppercase token", `Bearer AOC_${"1".repeat(64)}`],
  ]) {
    it(`rejects ${label} even with an ambient administrator session`, async () => {
      const response = await request("/v1/agent-identity", bearer, {
        cookie: "authjs.session-token=ambient-admin",
      });
      expect(response.status).toBe(401);
      expect(response.headers.get("cache-control")).toBe("no-store");
      expect(mocks.find).not.toHaveBeenCalled();
      expect(mocks.admin).not.toHaveBeenCalled();
    });
  }
  for (const scope of ["agent", "project", "organization"]) {
    it(`refuses foreign ${scope}`, async () => {
      const response = await request(
        scope === "agent"
          ? "/v1/agent-identity?agent=cto"
          : "/v1/agent-identity",
        `Bearer ${TOKEN}`,
        scope === "agent" ? {} : { [`x-${scope}-id`]: "foreign" },
      );
      expect(response.status).toBe(403);
      expect(mocks.admin).not.toHaveBeenCalled();
    });
  }
  it("checks revocation afresh rather than caching an earlier identity", async () => {
    const sameApp = app();
    const headers = { authorization: `Bearer ${TOKEN}` };
    expect(
      (await sameApp.request("/v1/agent-identity", { headers })).status,
    ).toBe(200);
    mocks.find.mockResolvedValue(null);
    expect(
      (await sameApp.request("/v1/agent-identity", { headers })).status,
    ).toBe(401);
    expect(mocks.find).toHaveBeenCalledTimes(2);
    expect(mocks.admin).not.toHaveBeenCalled();
  });
  it("does not enter the route on a lookup failure", async () => {
    mocks.find.mockRejectedValue(new Error("synthetic lookup unavailable"));
    const response = await request();
    expect(response.status).toBe(500);
    expect(await response.text()).not.toContain(TOKEN);
    expect(mocks.admin).not.toHaveBeenCalled();
  });
});
