import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import type { NextConfig } from "next";

// Keys the frontend reads from the repository-level .env so one file configures
// the API, the worker and this app. Already-exported variables win.
const SHARED_ENV_KEYS = ["API_BASE_URL", "NEXT_PUBLIC_API_BASE_URL", "INGEST_API_KEY"];

function loadSharedEnv() {
  const envPath = path.join(__dirname, "..", ".env");
  if (!existsSync(envPath)) return;
  for (const rawLine of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separator = line.indexOf("=");
    if (separator === -1) continue;
    const key = line.slice(0, separator).trim();
    if (!SHARED_ENV_KEYS.includes(key) || process.env[key] !== undefined) continue;
    let value = line.slice(separator + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (value) process.env[key] = value;
  }
}

loadSharedEnv();

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
