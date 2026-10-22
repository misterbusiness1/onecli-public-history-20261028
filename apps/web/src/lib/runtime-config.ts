import { readFileSync } from "fs";
import { EDITION, GOOGLE_CLIENT_ID, NEXTAUTH_SECRET } from "@/lib/env";

interface RuntimeConfig {
  authMode: "cloud" | "oauth" | "local" | "api-key";
  oauthConfigured: boolean;
}

const RUNTIME_CONFIG_PATH = "/app/data/runtime-config.json";

const CLOUD_CONFIG: RuntimeConfig = {
  authMode: "cloud",
  oauthConfigured: true,
};

let cached: RuntimeConfig | null = null;

/**
 * Reads the runtime config written by the Docker entrypoint at container start.
 * Cloud edition short-circuits (edition is a build-time decision).
 * Missing or invalid configuration requires authentication. Ambient local
 * administration is available only through the explicit development opt-in.
 */
export const getRuntimeConfig = (): RuntimeConfig => {
  if (EDITION === "cloud") return CLOUD_CONFIG;
  if (cached) return cached;

  const allowLocal = process.env.ONECLI_ALLOW_UNAUTHENTICATED_LOCAL === "true";

  try {
    const config: unknown = JSON.parse(
      readFileSync(RUNTIME_CONFIG_PATH, "utf-8"),
    );
    if (
      config &&
      typeof config === "object" &&
      "authMode" in config &&
      "oauthConfigured" in config &&
      typeof config.oauthConfigured === "boolean" &&
      (config.authMode === "oauth" ||
        config.authMode === "api-key" ||
        (config.authMode === "local" && allowLocal))
    ) {
      cached = config as RuntimeConfig;
      return cached;
    }
  } catch {
    // Missing/unreadable config uses the authenticated fallback below.
  }
  cached = {
    authMode: allowLocal ? "local" : NEXTAUTH_SECRET ? "oauth" : "api-key",
    oauthConfigured: !!GOOGLE_CLIENT_ID,
  };
  return cached;
};
