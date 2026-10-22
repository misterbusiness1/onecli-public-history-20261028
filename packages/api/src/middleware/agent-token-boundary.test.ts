import { beforeEach, describe, expect, it, vi } from "vitest";
import { Hono } from "hono";
import type { ApiEnv } from "../types";
const mocks = vi.hoisted(() => ({
  key: vi.fn(),
  session: vi.fn(),
}));
vi.mock("./auth/api-key", () => ({ authenticateApiKey: mocks.key }));
vi.mock("./auth/session", () => ({ authenticateSession: mocks.session }));
vi.mock("../providers", () => ({
  getRoleResolver: () => null,
  getStrictApiKeyAuth: () => false,
  ROLE_HIERARCHY: { owner: 3, admin: 2, member: 1 },
}));
import { auth } from "./auth";
describe("agent tokens never inherit a management session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.key.mockResolvedValue(null);
    mocks.session.mockResolvedValue({
      userId: "owner",
      userEmail: "owner@example.invalid",
      projectId: "project",
      organizationId: "org",
      scope: "session",
    });
  });
  for (const token of ["aoc_" + "1".repeat(64), "aoc_invalid"]) {
    it(`rejects an agent credential without consulting ambient auth (${token.length} chars)`, async () => {
      const app = new Hono<ApiEnv>();
      app.get("/agents", auth(), (c) => c.json({ admin: true }));
      const res = await app.request("/agents", {
        headers: { authorization: `Bearer ${token}` },
      });
      expect(res.status).toBe(401);
      expect(mocks.session).not.toHaveBeenCalled();
    });
  }
});
