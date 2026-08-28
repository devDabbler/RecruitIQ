import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      // `server-only` exists to *fail* the build when a server module is pulled
      // into a client bundle. Vitest is neither, so importing api.ts or
      // session.ts would throw on the import itself. Point it at an empty
      // module: the guard still protects the real build, where it matters.
      "server-only": fileURLToPath(new URL("./src/test/server-only.ts", import.meta.url)),
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    // These cover pure request/response plumbing, not rendering, so jsdom would
    // only add startup cost.
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
