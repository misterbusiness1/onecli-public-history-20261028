import type { AuthContext } from "./providers";

export type ApiEnv = {
  Variables: {
    auth: AuthContext;
    containerAgent?: {
      id: string;
      identifier: string;
      projectId: string;
      organizationId: string;
      accessToken: string;
    };
  };
};
