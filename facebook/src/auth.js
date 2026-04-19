import fs from "fs/promises";
import path from "path";

import { config } from "./config.js";

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function waitForHome(page, timeoutMs = config.loginTimeoutMs) {
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const url = page.url();
    if (!url.includes("/login")) {
      return true;
    }
    await page.waitForTimeout(500);
  }

  return false;
}

function isLoginUrl(url) {
  return url.includes("/login");
}

async function fillIfVisible(locator, value) {
  try {
    await locator.waitFor({ state: "visible", timeout: 2500 });
    await locator.fill(value);
    return true;
  } catch {
    return false;
  }
}

async function clickIfVisible(locator) {
  try {
    await locator.waitFor({ state: "visible", timeout: 2500 });
    await locator.click();
    return true;
  } catch {
    return false;
  }
}

export async function saveStorageState(context) {
  await fs.mkdir(path.dirname(config.storageStatePath), { recursive: true });
  await context.storageState({ path: config.storageStatePath });
}

export async function hasStoredSession() {
  return exists(config.storageStatePath);
}

export async function ensureFacebookLogin(page, context, options = {}) {
  const targetUrl = options.targetUrl || config.authTargetUrl || "https://www.facebook.com/";

  await page.goto(targetUrl, {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  });

  if (!isLoginUrl(page.url())) {
    await saveStorageState(context);
    return { authenticated: true, mode: "existing-session", targetUrl };
  }

  if (!config.loginEmail || !config.loginPassword) {
    throw new Error(
      "Facebook session expired and FB_LOGIN_EMAIL / FB_LOGIN_PASSWORD are not configured"
    );
  }

  const emailFilled = await fillIfVisible(
    page.locator('#email, input[name="email"], input[type="text"]').first(),
    config.loginEmail
  );
  const passwordFilled = await fillIfVisible(
    page.locator('#pass, input[name="pass"], input[type="password"]').first(),
    config.loginPassword
  );

  if (!emailFilled || !passwordFilled) {
    throw new Error("Could not locate Facebook login fields");
  }

  const clicked = await clickIfVisible(
    page.locator('button[name="login"], [data-testid="royal_login_button"], div[role="button"]').first()
  );
  if (!clicked) {
    await page.keyboard.press("Enter");
  }

  const loggedIn = await waitForHome(page);
  if (!loggedIn) {
    throw new Error("Facebook login did not complete successfully");
  }

  if (targetUrl && page.url() !== targetUrl) {
    await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
  }

  if (isLoginUrl(page.url())) {
    throw new Error("Facebook login succeeded but access to the target page still returned a login screen");
  }

  await saveStorageState(context);
  return { authenticated: true, mode: "env-login", targetUrl };
}
