import { beforeEach, describe, expect, it, vi } from "vitest";
import { Hono } from "hono";
import type { ApiEnv } from "../types";
const mocks = vi.hoisted(() => ({ find: vi.fn(), admin: vi.fn() }));
vi.mock("@onecli/db", () => ({ db: { agent: { findUnique: mocks.find } } }));
vi.mock("./auth", () => ({ authMiddleware: mocks.admin }));
import { containerAgentAuth } from "./container-agent-auth";
const TOKEN = "aoc_" + "1".repeat(64);
const app = () =>
  new Hono<ApiEnv>().get("/config", containerAgentAuth, (c) => {
    const p = c.get("containerAgent");
    return c.json({ agentId: p?.id, projectId: p?.projectId });
  });
describe("container configuration is bound to the bearer agent", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.find.mockResolvedValue({
      id: "agent-a",
      identifier: "worker-a",
      projectId: "project-a",
      accessToken: TOKEN,
      project: { organizationId: "org-a" },
    });
    mocks.admin.mockImplementation((c) => c.json({ administrative: true }));
  });
  it("uses the bearer identity when the caller omits the mutable selector", async () => {
    const res = await app().request("/config", {
      headers: { authorization: `Bearer ${TOKEN}` },
    });
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({
      agentId: "agent-a",
      projectId: "project-a",
    });
    expect(mocks.admin).not.toHaveBeenCalled();
  });
  it("accepts its own selector and matching scope headers", async () => {
    const res = await app().request("/config?agent=worker-a", {
      headers: {
        authorization: `Bearer ${TOKEN}`,
        "x-project-id": "project-a",
        "x-organization-id": "org-a",
      },
    });
    expect(res.status).toBe(200);
  });
  for (const scope of ["agent", "project", "organization"]) {
    it(`rejects a different ${scope} without falling back to an administrator`, async () => {
      const headers: Record<string, string> = {
        authorization: `Bearer ${TOKEN}`,
      };
      if (scope !== "agent") headers[`x-${scope}-id`] = "foreign";
      const res = await app().request(
        scope === "agent" ? "/config?agent=cto" : "/config",
        { headers },
      );
      expect(res.status).toBe(403);
      expect(mocks.admin).not.toHaveBeenCalled();
    });
  }
  it("rejects a revoked token without trying an ambient session", async () => {
    mocks.find.mockResolvedValue(null);
    const res = await app().request("/config", {
      headers: { authorization: `Bearer ${TOKEN}` },
    });
    expect(res.status).toBe(401);
    expect(mocks.admin).not.toHaveBeenCalled();
  });
  it("rejects malformed agent tokens before a database lookup", async () => {
    const res = await app().request("/config", {
      headers: { authorization: "Bearer aoc_bad" },
    });
    expect(res.status).toBe(401);
    expect(mocks.find).not.toHaveBeenCalled();
    expect(mocks.admin).not.toHaveBeenCalled();
  });
  it("retains the normal management authentication path for an administrative key", async () => {
    const res = await app().request("/config", {
      headers: { authorization: "Bearer oc_admin_fixture" },
    });
    expect(res.status).toBe(200);
    expect(mocks.admin).toHaveBeenCalledOnce();
    expect(mocks.find).not.toHaveBeenCalled();
  });
});
