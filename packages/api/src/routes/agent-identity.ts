import { Hono } from "hono";
import type { ApiEnv } from "../types";
import { assignedAgentAuth } from "../middleware/container-agent-auth";

/** Read-only self identity; never returns credentials or provisions an agent. */
export const agentIdentityRoutes = () => {
  const app = new Hono<ApiEnv>();
  app.use("*", async (c, next) => {
    c.header("Cache-Control", "no-store");
    c.header("Vary", "Authorization");
    await next();
  });
  app.use("*", assignedAgentAuth);
  app.get("/", (c) => {
    const agent = c.get("containerAgent");
    if (!agent) return c.json({ error: "Agent credential required" }, 401);
    return c.json({
      id: agent.id,
      identifier: agent.identifier,
      projectId: agent.projectId,
      organizationId: agent.organizationId,
    });
  });
  return app;
};
