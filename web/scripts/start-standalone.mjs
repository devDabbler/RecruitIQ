/**
 * Boot the standalone server bundle the same way the droplet will.
 *
 * `next start` prints "does not work with output: standalone" and is a
 * different code path from what Phase 4 deploys, so the e2e suite would be
 * proving something we never ship. This runs the real artifact.
 *
 * The copy step is not optional: `next build` deliberately leaves `.next/static`
 * and `public/` out of the standalone tree, on the assumption a CDN serves them.
 * Nothing serves them here, so without this the pages render unstyled and no
 * client bundle loads.
 *
 * Usage: node scripts/start-standalone.mjs [port]
 */
import { spawn } from "node:child_process";
import { cp, access } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const standalone = join(webRoot, ".next", "standalone");
const port = process.argv[2] ?? process.env.PORT ?? "3100";

const server = join(standalone, "server.js");
try {
  await access(server);
} catch {
  console.error(`No standalone build at ${server}. Run \`npm run build\` first.`);
  process.exit(1);
}

await cp(join(webRoot, ".next", "static"), join(standalone, ".next", "static"), {
  recursive: true,
});
await cp(join(webRoot, "public"), join(standalone, "public"), { recursive: true }).catch(
  () => {},
);

spawn(process.execPath, [server], {
  cwd: standalone,
  stdio: "inherit",
  env: { ...process.env, PORT: port, HOSTNAME: process.env.HOSTNAME ?? "127.0.0.1" },
}).on("exit", (code) => process.exit(code ?? 0));
