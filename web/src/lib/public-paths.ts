/**
 * Paths a candidate opens from an email (ATS Phase E). They never get a demo
 * session and never render the app shell.
 */
export const PUBLIC_PREFIXES = ["/c/"] as const;

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}
