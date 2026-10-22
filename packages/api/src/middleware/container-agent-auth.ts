import { createMiddleware } from "hono/factory";
import { db } from "@onecli/db";
import type { ApiEnv } from "../types";
import { authMiddleware } from "./auth";

/** Only container configuration accepts a gateway agent token as a credential. */
export const containerAgentAuth = createMiddleware<ApiEnv>(async (c, next) => {
  const header = c.req.header("authorization") ?? "";
  const match = /^Bearer\s+(aoc_\S*)$/i.exec(header);
  if (!match) return authMiddleware(c, next);
  const token = match[1] ?? "";
  if (!/^aoc_[a-f0-9]{64}$/.test(token)) {
    return c.json({ error: "Invalid agent credential" }, 401);
  }
  const agent = await db.agent.findUnique({
    where: { accessToken: token },
    select: {
      id: true,
      identifier: true,
      projectId: true,
      accessToken: true,
      project: { select: { organizationId: true } },
    },
  });
  if (!agent) return c.json({ error: "Invalid agent credential" }, 401);
  const selector = c.req.query("agent");
  const project = c.req.header("x-project-id");
  const organization = c.req.header("x-organization-id");
  if (
    (selector && selector !== agent.identifier) ||
    (project && project !== agent.projectId) ||
    (organization && organization !== agent.project.organizationId)
  ) {
    return c.json({ error: "Agent credential scope mismatch" }, 403);
  }
  c.set("containerAgent", {
    id: agent.id,
    identifier: agent.identifier,
    projectId: agent.projectId,
    accessToken: agent.accessToken,
    organizationId: agent.project.organizationId,
  });
  return next();
});
