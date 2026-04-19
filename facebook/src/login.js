import fs from "fs/promises";
import path from "path";
import readline from "readline/promises";
import { stdin as input, stdout as output } from "process";

import { chromium } from "playwright";

import { ensureFacebookLogin, saveStorageState } from "./auth.js";
import { config } from "./config.js";

async function main() {
  await fs.mkdir(path.dirname(config.storageStatePath), { recursive: true });
  await fs.mkdir(config.artifactsDir, { recursive: true });

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  const targetUrl = config.authTargetUrl || "https://www.facebook.com/";

  if (config.loginEmail && config.loginPassword) {
    const result = await ensureFacebookLogin(page, context, { targetUrl });
    console.log(
      `Saved auth state to ${config.storageStatePath} via ${result.mode} for ${result.targetUrl}`
    );
  } else {
    await page.goto(targetUrl, { waitUntil: "domcontentloaded" });
    console.log("");
    console.log("1. Log into Facebook in the opened browser");
    console.log("2. Open the target group once and confirm you can create a post");
    console.log("3. Return here and press Enter to save the session");
    console.log("");

    const rl = readline.createInterface({ input, output });
    await rl.question("Press Enter when the session is ready...");
    rl.close();

    await saveStorageState(context);
    console.log(`Saved auth state to ${config.storageStatePath}`);
  }

  await browser.close();
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
