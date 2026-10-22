import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  mode: vi.fn(),
  auth: vi.fn(),
  upsert: vi.fn(),
}));
vi.mock("@/lib/auth/nextauth-config", () => ({ auth: mocks.auth }));
vi.mock("@onecli/db", () => ({ db: { user: { upsert: mocks.upsert } } }));
vi.mock("@onecli/api/services/organization-service", () => ({
  findUserDefaultProject: vi.fn().mockResolvedValue({ id: "project" }),
  bootstrapOrganization: vi.fn(),
  joinSharedOrganization: vi.fn(),
}));
vi.mock("@/lib/env", () => ({ CAPS: { tenancy: "single-org-shared" } }));
vi.mock("./auth-mode", () => ({ getAuthMode: mocks.mode }));
import { getServerSessionImpl } from "./auth-server";
describe("API-key mode has no ambient administrative session", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  it("does not consult a browser session or bootstrap an owner in API-key mode", async () => {
    mocks.mode.mockReturnValue("api-key");
    mocks.auth.mockResolvedValue({
      user: { id: "unexpected", email: "unexpected@example.invalid" },
    });
    expect(await getServerSessionImpl()).toBeNull();
    expect(mocks.auth).not.toHaveBeenCalled();
    expect(mocks.upsert).not.toHaveBeenCalled();
  });
  it("still validates real sessions in OAuth mode", async () => {
    mocks.mode.mockReturnValue("oauth");
    mocks.auth.mockResolvedValue({
      user: {
        id: "verified-user",
        email: "verified@example.invalid",
        name: "Verified",
      },
    });
    expect(await getServerSessionImpl()).toEqual({
      id: "verified-user",
      email: "verified@example.invalid",
      name: "Verified",
    });
    expect(mocks.auth).toHaveBeenCalledOnce();
    expect(mocks.upsert).not.toHaveBeenCalled();
  });
});
