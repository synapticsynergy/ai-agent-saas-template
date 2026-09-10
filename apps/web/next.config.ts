import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { NextConfig } from "next";

/**
 * Load the repository-root `.env`.
 *
 * Next only reads `.env` from the app directory, but the template documents a
 * single root `.env` shared by the web app, the API, the agent and the MCP
 * server. Reading it here keeps that promise without duplicating configuration
 * or symlinking. Values already present in the environment win, so a shell
 * override or a container's `env_file` still takes precedence.
 */
function loadRootEnv(): void {
  try {
    const contents = readFileSync(resolve(import.meta.dirname, "../../.env"), "utf8");

    for (const line of contents.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) continue;

      const separator = trimmed.indexOf("=");
      if (separator === -1) continue;

      const key = trimmed.slice(0, separator).trim();
      const value = trimmed
        .slice(separator + 1)
        .trim()
        .replace(/^["']|["']$/g, "");

      if (!(key in process.env)) process.env[key] = value;
    }
  } catch {
    // No root .env — the app falls back to its own .env / .env.local, and
    // src/lib/env.ts reports anything genuinely missing at startup.
  }
}

loadRootEnv();

const config: NextConfig = {
  reactStrictMode: true,

  // The workspace contracts package is published as raw TypeScript.
  transpilePackages: ["@saas/contracts"],

  // Container deployments need the standalone output; inert elsewhere.
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
};

export default config;
