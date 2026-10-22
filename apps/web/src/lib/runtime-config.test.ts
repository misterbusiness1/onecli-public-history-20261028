import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ read: vi.fn(), secret: "" }));
vi.mock("fs", () => ({ readFileSync: mocks.read }));
vi.mock("@/lib/env", () => ({
  EDITION: "oss",
  GOOGLE_CLIENT_ID: "",
  get NEXTAUTH_SECRET() {
    return mocks.secret;
  },
}));

describe("runtime authentication configuration fails closed", () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.secret = "";
    mocks.read.mockImplementation(() => {
      throw new Error("missing");
    });
    vi.stubEnv("ONECLI_ALLOW_UNAUTHENTICATED_LOCAL", "false");
  });
  afterEach(() => vi.unstubAllEnvs());

  it.each([
    undefined,
    "{",
    "null",
    "{}",
    '{"authMode":"unknown","oauthConfigured":false}',
  ])(
    "does not grant ambient administration for invalid config %s",
    async (contents) => {
      if (contents !== undefined) mocks.read.mockReturnValue(contents);
      const { getRuntimeConfig } = await import("./runtime-config");
      expect(getRuntimeConfig().authMode).toBe("api-key");
    },
  );
  it("rejects stale local mode without explicit development opt-in", async () => {
    mocks.read.mockReturnValue('{"authMode":"local","oauthConfigured":false}');
    const { getRuntimeConfig } = await import("./runtime-config");
    expect(getRuntimeConfig().authMode).toBe("api-key");
  });
  it("retains authenticated OAuth fallback", async () => {
    mocks.secret = "synthetic-signing-secret";
    const { getRuntimeConfig } = await import("./runtime-config");
    expect(getRuntimeConfig().authMode).toBe("oauth");
  });
  it("permits explicit local development", async () => {
    vi.stubEnv("ONECLI_ALLOW_UNAUTHENTICATED_LOCAL", "true");
    const { getRuntimeConfig } = await import("./runtime-config");
    expect(getRuntimeConfig().authMode).toBe("local");
  });
});
