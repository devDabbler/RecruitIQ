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
import { can, PIPELINE_MOVE, type Permission, type Role } from "./permissions";

export type { Role } from "./permissions";

export interface SessionUser {
  id: string;
  email: string;
  name: string | null;
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
 * Whether the current session may move candidates through the pipeline
 * (admin, hiring manager, hiring team). Kept under its Phase A name because
 * the candidate page's stage actions are what it gates.
 *
 * Used only to hide controls. The real gate is `enforce_read_only` in the
 * backend: a hidden button is not an access control (spec section 2).
 */
export async function canWrite(): Promise<boolean> {
  return hasPermission(PIPELINE_MOVE);
}

/** Whether the current session holds one permission from the generated table. */
export async function hasPermission(permission: Permission): Promise<boolean> {
  const user = await getUser();
  return can(user?.role, permission);
}
