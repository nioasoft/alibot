import fs from "fs/promises";
import path from "path";

import pino from "pino";
import { chromium } from "playwright";

import { config } from "./config.js";

const logger = pino({ level: process.env.LOG_LEVEL || "info" });

const CREATE_POST_SELECTORS = [
  'div[role="button"][aria-label*="כאן כותבים"]',
  'div[role="button"][aria-label*="What\'s on your mind"]',
  'div[role="button"][aria-label*="Write something"]',
  'div[role="button"][aria-label*="Create a public post"]',
  'div[role="button"][aria-label*="צור פוסט"]',
  'div[role="button"][aria-label*="מה עובר לך בראש"]',
  'div[role="button"][aria-label*="כתוב משהו"]',
  'div[role="button"][aria-label*="מה את"]',
  'div[role="button"][aria-label*="על מה את"]',
];

const POST_BUTTON_SELECTORS = [
  'div[role="button"][aria-label="Post"]',
  'div[role="button"][aria-label="Publish"]',
  'div[role="button"][aria-label="פרסום"]',
  'div[role="button"][aria-label="פרסם"]',
];

const FILE_INPUT_SELECTORS = [
  'input[type="file"]',
  'input[accept*="image"]',
];

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

async function ensureDir(dirPath) {
  await fs.mkdir(dirPath, { recursive: true });
}

async function firstVisible(page, selectors, timeout = 3000) {
  for (const selector of selectors) {
    const locator = page.locator(selector).first();
    try {
      await locator.waitFor({ state: "visible", timeout });
      return locator;
    } catch {
      // try next selector
    }
  }
  return null;
}

async function openComposer(page) {
  const directTextTriggers = [
    page.getByText(/כאן כותבים/i).first(),
    page.getByText(/מה את חושבת|מה אתה חושב|על מה את חושבת|על מה אתה חושב/i).first(),
    page.getByText(/כתוב משהו|write something|create post/i).first(),
  ];

  for (const trigger of directTextTriggers) {
    try {
      await trigger.waitFor({ state: "visible", timeout: 2000 });
      await trigger.click();
      await page.waitForTimeout(1500);

      const dialogComposer = page.locator('[role="dialog"] div[contenteditable="true"]').first();
      try {
        await dialogComposer.waitFor({ state: "visible", timeout: 2000 });
        await dialogComposer.click();
        return dialogComposer;
      } catch {
        // continue to other trigger strategies
      }
    } catch {
      // try next direct trigger
    }
  }

  const createButton = await firstVisible(page, CREATE_POST_SELECTORS, 5000);
  if (createButton) {
    await createButton.click();
    await page.waitForTimeout(1500);
  }

  const dialogComposer = page.locator('[role="dialog"] div[contenteditable="true"]').first();
  try {
    await dialogComposer.waitFor({ state: "visible", timeout: 4000 });
    await dialogComposer.click();
    return dialogComposer;
  } catch {
    // fall through to inline composer flow
  }

  const triggerPatterns = [
    /כאן כותבים|מה את חושבת|מה אתה חושב|על מה את חושבת|על מה אתה חושב/i,
    /כתוב משהו|write something|create post/i,
  ];

  for (const pattern of triggerPatterns) {
    const trigger = page.getByText(pattern).first();
    try {
      await trigger.waitFor({ state: "visible", timeout: 3000 });
      await trigger.click();
      await page.waitForTimeout(1200);

      const focusedComposer = page.locator('div[contenteditable="true"]:focus').first();
      try {
        await focusedComposer.waitFor({ state: "visible", timeout: 1500 });
        return focusedComposer;
      } catch {
        // continue to next candidate
      }

      const textboxComposer = page.locator('div[role="textbox"][contenteditable="true"]').first();
      await textboxComposer.waitFor({ state: "visible", timeout: 2000 });
      await textboxComposer.click();
      return textboxComposer;
    } catch {
      // try next pattern
    }
  }

  const textTrigger = page.getByText(/כאן כותבים|מה את חושבת|מה אתה חושב|על מה את חושבת|כתוב משהו|write something/i).first();
  try {
    await textTrigger.waitFor({ state: "visible", timeout: 3000 });
    await textTrigger.click();
    const fallbackComposer = page.locator('div[role="textbox"][contenteditable="true"]').first();
    await fallbackComposer.waitFor({ state: "visible", timeout: 5000 });
    return fallbackComposer;
  } catch {
    throw new Error("Could not locate Facebook post composer");
  }
}

async function uploadImage(page, imagePath) {
  if (!imagePath) {
    return;
  }

  const resolved = path.resolve(imagePath);
  if (!(await exists(resolved))) {
    throw new Error(`Image file not found: ${resolved}`);
  }

  const dialog = page.locator('[role="dialog"]').first();

  let fileInput = await firstVisible(dialog, FILE_INPUT_SELECTORS, 2000);
  if (fileInput == null) {
    const uploadCandidates = [
      dialog.getByRole("button", { name: /photo|image|תמונה|תמונות/i }).first(),
      dialog.getByText(/photo|image|תמונה|תמונות/i).first(),
      dialog.locator('[aria-label*="photo"], [aria-label*="image"], [aria-label*="תמונה"]').first(),
      dialog.locator('div[role="button"]').nth(3),
    ];

    for (const candidate of uploadCandidates) {
      try {
        await candidate.waitFor({ state: "visible", timeout: 1500 });
        const fileChooserPromise = page.waitForEvent("filechooser", { timeout: 4000 });
        await candidate.click();
        const chooser = await fileChooserPromise;
        await chooser.setFiles(resolved);
        return;
      } catch {
        // try next candidate
      }
    }

    fileInput = await firstVisible(dialog, FILE_INPUT_SELECTORS, 2000);
  }

  if (fileInput == null) {
    throw new Error("Could not locate file input for image upload");
  }

  await fileInput.setInputFiles(resolved);
}

async function clickPost(page) {
  const button = await firstVisible(page, POST_BUTTON_SELECTORS, 5000);
  if (button == null) {
    const fallback = page.getByRole("button", { name: /post|publish|פרסם|פרסום/i }).last();
    await fallback.waitFor({ state: "visible", timeout: 5000 });
    await fallback.click();
    return;
  }
  await button.click();
}

async function waitForPreview(page) {
  await page.waitForTimeout(config.previewWaitMs);
}

async function assertSessionFile() {
  if (!(await exists(config.storageStatePath))) {
    throw new Error(
      `Missing Facebook auth state at ${config.storageStatePath}. Run 'npm run auth' in facebook/ first.`
    );
  }
}

export async function openAuthenticatedContext() {
  await assertSessionFile();
  await ensureDir(config.artifactsDir);

  const browser = await chromium.launch({ headless: config.headless });
  const context = await browser.newContext({
    storageState: config.storageStatePath,
    viewport: { width: 1440, height: 1100 },
  });
  const page = await context.newPage();
  return { browser, context, page };
}

export async function publishToFacebookGroup({
  groupUrl,
  text,
  imagePath = "",
  appendText = "",
  dryRun = false,
}) {
  if (!groupUrl) {
    throw new Error("groupUrl is required");
  }
  if (!text || !text.trim()) {
    throw new Error("text is required");
  }

  const { browser, page } = await openAuthenticatedContext();
  const startedAt = Date.now();

  try {
    logger.info({ groupUrl, dryRun }, "Opening Facebook group");
    await page.goto(groupUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(3000);

    if (page.url().includes("/login")) {
      throw new Error("Facebook session is not authenticated");
    }

    const composer = await openComposer(page);
    await composer.fill(text);

    if (appendText && appendText.trim()) {
      await waitForPreview(page);
      await composer.press("End");
      await page.waitForTimeout(300);
      await composer.type(appendText, { delay: 15 });
    }

    if (imagePath) {
      await uploadImage(page, imagePath);
      await page.waitForTimeout(3000);
    }

    await waitForPreview(page);

    const screenshotPath = path.join(
      config.artifactsDir,
      `facebook-compose-${Date.now()}.png`
    );
    await page.screenshot({ path: screenshotPath, fullPage: true });

    if (dryRun) {
      logger.info({ screenshotPath }, "Dry run complete; not clicking Post");
      return {
        ok: true,
        mode: "dry-run",
        screenshotPath,
        elapsedMs: Date.now() - startedAt,
      };
    }

    await clickPost(page);
    await page.waitForTimeout(5000);

    return {
      ok: true,
      mode: "live",
      screenshotPath,
      elapsedMs: Date.now() - startedAt,
    };
  } catch (error) {
    const errorPath = path.join(
      config.artifactsDir,
      `facebook-error-${Date.now()}.png`
    );
    try {
      await page.screenshot({ path: errorPath, fullPage: true });
    } catch {
      // ignore screenshot failure
    }
    logger.error({ err: error, errorPath }, "Facebook publish failed");
    throw error;
  } finally {
    await browser.close();
  }
}
