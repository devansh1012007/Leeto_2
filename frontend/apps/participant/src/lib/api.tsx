/**
 * Auth + API wiring (ATH-01/AT-01): token lifecycle in localStorage, a shared ParticipantClient
 * bound to the token, and a React context. The client never decides routes (T-5.2);
 * pages call `useApi()` and handle failures with copy-catalog strings.
 */
import React from "react";
import { ParticipantClient } from "@bhctf/api-client";

const TOKEN_KEY = "bhctf.access_token";
const REFRESH_KEY = "bhctf.refresh_token";

/** Base URL of the participant API ("" = same origin; override for local dev). */
export const API_BASE: string =
  (typeof window !== "undefined" && window.localStorage.getItem("bhctf.api_base")) || "";

export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function storeTokens(access: string, refresh?: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, access);
    if (refresh !== undefined) localStorage.setItem(REFRESH_KEY, refresh);
  } catch {
    /* private mode: session-only auth */
  }
}

export function clearTokens(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* ignore */
  }
}

export function makeClient(token?: string | null): ParticipantClient {
  return new ParticipantClient({ baseUrl: API_BASE, token: token ?? getAccessToken() ?? undefined });
}

export function newIdempotencyKey(): string {
  const c = typeof crypto !== "undefined" ? crypto : undefined;
  if (c && "randomUUID" in c) return c.randomUUID();
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export interface ApiContextValue {
  api: ParticipantClient;
  signedIn: boolean;
  signIn: (identifier: string, password: string) => Promise<{ ok: boolean; error?: string }>;
  signOut: () => Promise<void>;
}

const ApiContext = React.createContext<ApiContextValue | null>(null);

export function ApiProvider(props: {
  children: React.ReactNode;
  signedIn?: boolean; // test override: false forces signed-out rendering
}): React.JSX.Element {
  const [token, setToken] = React.useState<string | null>(
    props.signedIn === false ? null : getAccessToken(),
  );
  const api = React.useMemo(() => makeClient(token), [token]);

  React.useEffect(() => {
    api.setToken(token ?? undefined);
  }, [api, token]);

  const signIn = React.useCallback(async (identifier: string, password: string) => {
    const client = new ParticipantClient({ baseUrl: API_BASE });
    try {
      const res = (await client.post_v1_auth_login({ identifier, password })) as {
        data?: { access_token?: string; refresh_token?: string };
      };
      const access = res?.data?.access_token;
      if (!access) return { ok: false, error: "AUTH_INVALID_CREDENTIALS" };
      storeTokens(access, res?.data?.refresh_token);
      setToken(access);
      return { ok: true };
    } catch (err) {
      const code = (err as { code?: string }).code || "INTERNAL";
      return { ok: false, error: code };
    }
  }, []);

  const signOut = React.useCallback(async () => {
    try {
      await api.post_v1_auth_logout();
    } catch {
      /* best-effort: local sign-out always proceeds */
    }
    clearTokens();
    setToken(null);
  }, [api]);

  const value = React.useMemo<ApiContextValue>(
    () => ({ api, signedIn: token !== null, signIn, signOut }),
    [api, token, signIn, signOut],
  );

  return <ApiContext.Provider value={value}>{props.children}</ApiContext.Provider>;
}

export function useApi(): ApiContextValue {
  const ctx = React.useContext(ApiContext);
  if (!ctx) {
    // outside a provider (tests): a detached client
    return { api: makeClient(), signedIn: false, signIn: async () => ({ ok: false }), signOut: async () => {} };
  }
  return ctx;
}
