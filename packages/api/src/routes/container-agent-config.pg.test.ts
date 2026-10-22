import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { Hono } from "hono";
import type { ApiEnv } from "../types";
import { proofDatabaseUrl } from "../testing/pg-proof";
vi.mock("../lib/gateway-ca", () => ({
  loadCaCertificate: () => "synthetic-public-ca-fixture",
}));
const url = proofDatabaseUrl();
const PREFIX = "identity-proof-";
const TOKEN_A = "aoc_" + "a".repeat(64);
const TOKEN_B = "aoc_" + "b".repeat(64);
let db: typeof import("@onecli/db").db;
let app: Hono<ApiEnv>;
const cleanup = async () => {
  await db.agent.deleteMany({ where: { id: { startsWith: PREFIX } } });
  await db.project.deleteMany({ where: { id: { startsWith: PREFIX } } });
  await db.organization.deleteMany({ where: { id: { startsWith: PREFIX } } });
};
beforeAll(async () => {
  if (!url) return;
  process.env.DATABASE_URL = url;
  ({ db } = await import("@onecli/db"));
  await cleanup();
  for (const [name, token] of [
    ["a", TOKEN_A],
    ["b", TOKEN_B],
  ] as const) {
    await db.organization.create({
      data: { id: PREFIX + "org-" + name, name, slug: PREFIX + name },
    });
    await db.project.create({
      data: {
        id: PREFIX + "project-" + name,
        organizationId: PREFIX + "org-" + name,
        name,
      },
    });
    await db.agent.create({
      data: {
        id: PREFIX + "agent-" + name,
        identifier: "worker-" + name,
        name,
        projectId: PREFIX + "project-" + name,
        accessToken: token,
        secretMode: "selective",
        isDefault: true,
      },
    });
  }
  const { initSession } = await import("../providers");
  initSession({ getSession: async () => null });
  const { containerConfigRoutes } = await import("./container-config");
  const { agentRoutes } = await import("./agents");
  app = new Hono<ApiEnv>();
  app.route("/config", containerConfigRoutes());
  app.route("/agents", agentRoutes());
});
afterAll(async () => {
  if (url && db) {
    await cleanup();
    await db.$disconnect();
  }
});
const get = (path: string, token = TOKEN_A, headers = {}) =>
  app.request(path, {
    headers: { authorization: `Bearer ${token}`, ...headers },
  });
describe.skipIf(!url)(
  "actual configuration route and PostgreSQL principal binding",
  () => {
    it("returns only its token even when the identity selector is omitted", async () => {
      const res = await get("/config");
      expect(res.status).toBe(200);
      const config = await res.json();
      expect(config.env.HTTPS_PROXY).toContain(TOKEN_A);
      expect(JSON.stringify(config)).not.toContain(TOKEN_B);
    });
    it("rejects selecting another registered company's agent", async () => {
      expect((await get("/config?agent=worker-b")).status).toBe(403);
    });
    it("rejects a foreign project header", async () => {
      expect(
        (
          await get("/config", TOKEN_A, {
            "x-project-id": PREFIX + "project-b",
          })
        ).status,
      ).toBe(403);
    });
    it("does not turn an agent token into management access", async () => {
      expect((await get("/agents")).status).toBe(401);
    });
    it("refuses missing credentials", async () => {
      expect((await app.request("/config")).status).toBe(401);
    });
    it("refuses revoked credentials rather than using the default agent", async () => {
      await db.agent.update({
        where: { id: PREFIX + "agent-b" },
        data: { accessToken: "aoc_" + "c".repeat(64) },
      });
      expect((await get("/config", TOKEN_B)).status).toBe(401);
    });
  },
);
