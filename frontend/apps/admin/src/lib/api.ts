/** Admin API hook: shared ApiClient for the admin SPA. Token comes from the
 * bhctf.admin_token localStorage slot set by the admin sign-in. */
import React from "react";
import { ApiClient } from "@bhctf/api-client";

const ADMIN_TOKEN_KEY = "bhctf.admin_token";

export function getAdminToken(): string | null {
  try {
    return localStorage.getItem(ADMIN_TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setAdminToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(ADMIN_TOKEN_KEY, token);
    else localStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export function useAdminApi(): ApiClient {
  const token = getAdminToken();
  return React.useMemo(
    () => new ApiClient({ baseUrl: "", token: token ?? undefined }),
    [token],
  );
}
