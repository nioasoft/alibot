import path from "path";
import { fileURLToPath } from "url";

import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(projectRoot, "..");

dotenv.config({ path: path.join(repoRoot, ".env") });
dotenv.config({ path: path.join(projectRoot, ".env"), override: true });

function parseBoolean(value, fallback = false) {
  if (value == null || value === "") {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(String(value).toLowerCase());
}

export const config = {
  repoRoot,
  projectRoot,
  defaultGroupUrl: process.env.FB_GROUP_URL || "",
  authTargetUrl: process.env.FB_AUTH_TARGET_URL || process.env.FB_GROUP_URL || "",
  serverHost: process.env.FB_SERVER_HOST || "127.0.0.1",
  headless: parseBoolean(process.env.FB_HEADLESS, false),
  storageStatePath: path.resolve(projectRoot, process.env.FB_STORAGE_STATE || ".auth/facebook.json"),
  artifactsDir: path.resolve(projectRoot, process.env.FB_ARTIFACTS_DIR || "artifacts"),
  serverPort: Number(process.env.FB_SERVER_PORT || 3002),
  previewWaitMs: Number(process.env.FB_PREVIEW_WAIT_MS || 5000),
  loginTimeoutMs: Number(process.env.FB_LOGIN_TIMEOUT_MS || 30000),
  publishConfirmTimeoutMs: Number(process.env.FB_PUBLISH_CONFIRM_TIMEOUT_MS || 15000),
  loginEmail:
    process.env.FB_LOGIN_EMAIL ||
    process.env.FB_EMAIL ||
    process.env.FACEBOOK_EMAIL ||
    process.env.USERNAME ||
    "",
  loginPassword:
    process.env.FB_LOGIN_PASSWORD ||
    process.env.FB_PASSWORD ||
    process.env.FACEBOOK_PASSWORD ||
    process.env.PASSWORD ||
    "",
};
