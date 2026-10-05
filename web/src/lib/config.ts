/**
 * Server-side configuration.
 *
 * None of these are `NEXT_PUBLIC_`, and that is deliberate: the browser never
 * talks to FastAPI directly (Phase 3 spec §1). It talks to Next, which holds
 * the API base URL and the session cookie. A `NEXT_PUBLIC_API_URL` would leak
 * the backend origin into the client bundle and invite someone to call it.
 */

import { parseDeploymentMode, type DeploymentMode } from "./deployment";

export const API_BASE_URL = (
  process.env.API_BASE_URL ?? "http://127.0.0.1:8010"
).replace(/\/$/, "");

/**
 * `public` (default) or `internal`; see lib/deployment.ts. Read from the web
 * process's own environment (on the droplet, /etc/recruitiq/web.env), and
 * it must match the API's DEPLOYMENT_MODE: the API is the gate, this only
 * decides the shell's copy and where a signed-out visitor is sent.
 */
export const DEPLOYMENT_MODE: DeploymentMode = parseDeploymentMode(process.env.DEPLOYMENT_MODE);
export const IS_INTERNAL = DEPLOYMENT_MODE === "internal";

/** Name of the httpOnly cookie holding the JWT. */
export const SESSION_COOKIE = "recruitiq_session";

/**
 * Secure cookies require HTTPS, which local development does not have. Keying
 * this off NODE_ENV rather than a hand-set flag means production cannot
 * accidentally ship a non-Secure session cookie.
 */
export const COOKIE_SECURE = process.env.NODE_ENV === "production";
