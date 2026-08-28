import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Ships a self-contained server bundle so the droplet does not need a
  // node_modules tree. Phase 3 spec §1: this runs as a systemd unit with
  // MemoryMax=512M, behind nginx.
  output: "standalone",

  // The repository root is the workspace root, not web/. Without this, Next
  // traces files from web/ and the standalone bundle misses nothing today but
  // warns about the ambiguous root on every build.
  outputFileTracingRoot: process.cwd(),

  // Dev-only: Next 16 blocks /_next resources for any host but "localhost",
  // and a browser (or Playwright) pointed at 127.0.0.1 gets 403s on every
  // chunk — pages then SSR fine but never hydrate, so nothing is clickable.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
