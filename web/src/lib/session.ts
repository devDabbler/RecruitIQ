/**
 * Reading the session inside Server Components (Phase 3 spec §2).
 *
 * The token is set by `proxy.ts` before the request reaches a page, so by the
 * time anything here runs the cookie exists. `getToken` still tolerates its
 * absence — a Server Component that renders during an error path should show
 * an unauthenticated page, not throw.
 */
import "server-only";

import { cookies } from "next/headers";

import { apiFetch } from "./api";
import { SESSION_COOKIE } from "./config";

export type Role = "admin" | "demo";

export interface SessionUser {
  id: string;
  email: string;
  role: Role;
  created_at: string;
}

/** The raw JWT, or null when the request arrived without a session cookie. */
export async function getToken(): Promise<string | null> {
  // `cookies()` is async as of Next 15 and must be awaited.
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

/**
 * The signed-in user, or null.
 *
 * Asks the API rather than decoding the JWT locally: verifying a signature
 * needs the secret, and an unverified decode is not an authentication check.
 * The extra loopback call is cheap and keeps the secret in one process.
 */
export async function getUser(): Promise<SessionUser | null> {
  const token = await getToken();
  if (!token) return null;

  try {
    return await apiFetch<SessionUser>("/auth/me", { token });
  } catch {
    // Expired or malformed token. Treat as signed out; `proxy.ts` issues a
    // fresh demo token on the next request.
    return null;
  }
}

/**
 * Whether the current session may write.
 *
 * Used only to hide mutating controls. The real gate is `enforce_read_only` in
 * the backend — a hidden button is not an access control (spec §2).
 */
export async function canWrite(): Promise<boolean> {
  const user = await getUser();
  return user?.role === "admin";
}
