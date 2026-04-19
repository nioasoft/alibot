import fs from "fs/promises";

import express from "express";
import { chromium } from "playwright";

import { ensureFacebookLogin } from "./auth.js";
import { config } from "./config.js";
import { publishToFacebookGroup } from "./facebookPoster.js";

const app = express();
app.use(express.json({ limit: "2mb" }));

let activePublish = Promise.resolve();

function enqueue(task) {
  activePublish = activePublish.then(task, task);
  return activePublish;
}

function parseBoolean(value) {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return ["1", "true", "yes", "on"].includes(value.toLowerCase());
  }
  return Boolean(value);
}

app.get("/health", async (req, res) => {
  let authReady = false;
  try {
    await fs.access(config.storageStatePath);
    authReady = true;
  } catch {
    authReady = false;
  }

  res.json({
    status: "ok",
    authReady,
    defaultGroupUrl: config.defaultGroupUrl || null,
    headless: config.headless,
  });
});

app.post("/publish", async (req, res) => {
  const payload = {
    groupUrl: req.body.group_url || req.body.groupUrl || config.defaultGroupUrl,
    text: req.body.text || "",
    imagePath: req.body.image_path || req.body.imagePath || "",
    appendText: req.body.append_text || req.body.appendText || "",
    dryRun: parseBoolean(req.body.dry_run ?? req.body.dryRun),
  };

  try {
    const result = await enqueue(() => publishToFacebookGroup(payload));
    res.json(result);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

app.post("/refresh-auth", async (req, res) => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const targetUrl = req.body.group_url || req.body.groupUrl || config.authTargetUrl;

  try {
    const result = await ensureFacebookLogin(page, context, { targetUrl });
    res.json({
      ok: true,
      mode: result.mode,
      targetUrl: result.targetUrl,
      storageStatePath: config.storageStatePath,
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    });
  } finally {
    await browser.close();
  }
});

app.listen(config.serverPort, config.serverHost, () => {
  console.log(`Facebook POC service listening on http://${config.serverHost}:${config.serverPort}`);
});
