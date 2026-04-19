import fs from "fs/promises";
import path from "path";

import pino from "pino";
import { chromium } from "playwright";

import { ensureFacebookLogin, hasStoredSession, saveStorageState } from "./auth.js";
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

const PUBLISH_SUCCESS_PATTERNS = [
  /your post was shared/i,
  /post published/i,
  /post shared/i,
  /הפוסט שלך פורסם/i,
  /הפוסט פורסם/i,
];

const PUBLISH_FAILURE_PATTERNS = [
  /try again/i,
  /couldn'?t post/i,
  /something went wrong/i,
  /we limit how often/i,
  /unable to post/i,
  /נסה שוב/i,
  /לא הצלחנו/i,
  /משהו השתבש/i,
  /הפעולה נחסמה/i,
];

const FILE_INPUT_SELECTORS = [
  'input[type="file"]',
  'input[type="file"][accept*="image"]',
  'input[accept*="image"]',
];

const ATTACHMENT_READY_SELECTORS = [
  'img[src^="blob:"]',
  'img[src^="data:"]',
  '[aria-label*="Remove photo"]',
  '[aria-label*="Delete photo"]',
  '[aria-label*="הסר תמונה"]',
  '[aria-label*="מחק תמונה"]',
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

async function firstAttached(scope, selectors, timeout = 3000) {
  for (const selector of selectors) {
    const locator = scope.locator(selector).first();
    try {
      await locator.waitFor({ state: "attached", timeout });
      return locator;
    } catch {
      // try next selector
    }
  }
  return null;
}

async function isVisible(locator) {
  try {
    return await locator.isVisible();
  } catch {
    return false;
  }
}

async function openComposer(page) {
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForTimeout(800);

  const directTextTriggers = [
    page.getByText(/כאן כותבים/i).first(),
    page.getByText(/מה את חושבת|מה אתה חושב|על מה את חושבת|על מה אתה חושב/i).first(),
    page.getByText(/כתוב משהו|write something|create post/i).first(),
    page.getByText(/כתבו משהו|שתפו משהו|מה חדש|יצירת פוסט/i).first(),
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
    /כתוב משהו|כתבו משהו|write something|create post|share something|what's on your mind|what are you thinking/i,
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

  const genericComposerButtons = [
    page.locator('div[role="button"][aria-label*="post"]').first(),
    page.locator('div[role="button"][aria-label*="פרסם"]').first(),
    page.locator('div[role="button"][aria-label*="כתוב"]').first(),
    page.locator('div[role="button"][aria-label*="שתף"]').first(),
  ];

  for (const candidate of genericComposerButtons) {
    try {
      await candidate.waitFor({ state: "visible", timeout: 1500 });
      await candidate.click();
      const fallbackComposer = page.locator('div[role="textbox"][contenteditable="true"]').first();
      await fallbackComposer.waitFor({ state: "visible", timeout: 3000 });
      return fallbackComposer;
    } catch {
      // try next fallback
    }
  }

  const textTrigger = page.getByText(/כאן כותבים|מה את חושבת|מה אתה חושב|על מה את חושבת|כתוב משהו|כתבו משהו|שתפו משהו|write something/i).first();
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

async function waitForImageAttachment(page, dialog, initialImageCount) {
  const deadline = Date.now() + 10000;

  while (Date.now() < deadline) {
    const imageCount = await dialog.locator("img").count();
    if (imageCount > initialImageCount) {
      return { confirmation: "image-count-incremented", imageCount };
    }

    const attachmentReady = await firstVisible(dialog, ATTACHMENT_READY_SELECTORS, 250);
    if (attachmentReady != null) {
      return { confirmation: "attachment-selector-visible" };
    }

    await page.waitForTimeout(250);
  }

  throw new Error("Image upload did not produce a visible attachment in the Facebook composer");
}

async function setFilesAndConfirm(page, dialog, locator, resolved, initialImageCount) {
  await locator.setInputFiles(resolved);
  return waitForImageAttachment(page, dialog, initialImageCount);
}

async function uploadImage(page, imagePath, dialog) {
  if (!imagePath) {
    return;
  }

  const resolved = path.resolve(imagePath);
  if (!(await exists(resolved))) {
    throw new Error(`Image file not found: ${resolved}`);
  }

  const composerDialog = dialog ?? page.locator('[role="dialog"]').first();
  const initialImageCount = await composerDialog.locator("img").count();
  const uploadCandidates = [
    composerDialog.getByRole("button", { name: /photo|image|video|photo\/video|תמונה|תמונות|וידאו|סרטון/i }).first(),
    composerDialog.getByText(/photo|image|video|photo\/video|תמונה|תמונות|וידאו|סרטון/i).first(),
    composerDialog.locator('[aria-label*="photo"], [aria-label*="image"], [aria-label*="video"], [aria-label*="תמונה"], [aria-label*="וידאו"]').first(),
    composerDialog.locator('div[role="button"]').nth(3),
  ];

  const genericButtons = (await composerDialog.locator('div[role="button"]').all()).slice(-12);
  const buttonCandidates = [...uploadCandidates, ...genericButtons];

  for (const candidate of buttonCandidates) {
    try {
      await candidate.waitFor({ state: "visible", timeout: 1200 });
    } catch {
      continue;
    }

    try {
      try {
        const fileChooserPromise = page.waitForEvent("filechooser", { timeout: 1500 });
        await candidate.click({ force: true });
        const chooser = await fileChooserPromise;
        await chooser.setFiles(resolved);
        return waitForImageAttachment(page, composerDialog, initialImageCount);
      } catch {
        await candidate.click({ force: true });
      }

      let fileInput = await firstAttached(composerDialog, FILE_INPUT_SELECTORS, 1000);
      if (fileInput == null) {
        fileInput = await firstAttached(page, FILE_INPUT_SELECTORS, 1000);
      }
      if (fileInput != null) {
        return await setFilesAndConfirm(
          page,
          composerDialog,
          fileInput,
          resolved,
          initialImageCount,
        );
      }
    } catch {
      try {
        await page.keyboard.press("Escape");
      } catch {
        // ignore escape failures while probing upload controls
      }
    }
  }

  const rawInputs = [
    await firstAttached(composerDialog, FILE_INPUT_SELECTORS, 1000),
    await firstAttached(page, FILE_INPUT_SELECTORS, 1000),
  ].filter(Boolean);

  for (const fileInput of rawInputs) {
    try {
      return await setFilesAndConfirm(
        page,
        composerDialog,
        fileInput,
        resolved,
        initialImageCount,
      );
    } catch {
      // try next raw input
    }
  }

  throw new Error("Could not upload image through any Facebook composer control");
}

async function clickPost(page) {
  const button = await firstVisible(page, POST_BUTTON_SELECTORS, 5000);
  if (button == null) {
    const fallback = page.getByRole("button", { name: /post|publish|פרסם|פרסום/i }).last();
    await fallback.waitFor({ state: "visible", timeout: 5000 });
    await fallback.click();
    return fallback;
  }
  await button.click();
  return button;
}

async function waitForPreview(page) {
  await page.waitForTimeout(config.previewWaitMs);
}

async function ensureGroupPageReady(page, context, groupUrl) {
  const authResult = await ensureFacebookLogin(page, context, { targetUrl: groupUrl });
  logger.info({ authMode: authResult.mode, groupUrl }, "Opening Facebook group");

  if (page.url() !== groupUrl) {
    await page.goto(groupUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  }

  await page.waitForTimeout(3000);

  if (page.url().includes("/login")) {
    const retryAuth = await ensureFacebookLogin(page, context, { targetUrl: groupUrl });
    logger.info(
      { authMode: retryAuth.mode, groupUrl },
      "Re-authenticated after Facebook redirected to login"
    );
    await page.goto(groupUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(3000);
  }
}

async function openComposerWithRecovery(page, context, groupUrl) {
  try {
    return await openComposer(page);
  } catch (error) {
    logger.warn(
      { err: error, groupUrl },
      "Failed to open Facebook composer; refreshing auth and retrying the group page once"
    );
    await ensureGroupPageReady(page, context, groupUrl);
    return openComposer(page);
  }
}

async function findVisibleText(scope, patterns) {
  for (const pattern of patterns) {
    const locator = scope.getByText(pattern).first();
    if (await isVisible(locator)) {
      return pattern.source;
    }
  }
  return null;
}

async function waitForPublishConfirmation(page, { dialog, postButton }) {
  const deadline = Date.now() + config.publishConfirmTimeoutMs;

  while (Date.now() < deadline) {
    const failureText = await findVisibleText(page, PUBLISH_FAILURE_PATTERNS);
    if (failureText) {
      throw new Error(`Facebook showed a publish failure message: ${failureText}`);
    }

    const successText = await findVisibleText(page, PUBLISH_SUCCESS_PATTERNS);
    if (successText) {
      return { confirmation: "success-message", details: successText };
    }

    if (dialog && !(await isVisible(dialog))) {
      return { confirmation: "composer-closed" };
    }

    if (postButton && !(await isVisible(postButton))) {
      return { confirmation: "post-button-hidden" };
    }

    await page.waitForTimeout(250);
  }

  throw new Error("Clicked Post but could not confirm that Facebook accepted the publish action");
}

export async function openAuthenticatedContext() {
  await ensureDir(config.artifactsDir);

  const browser = await chromium.launch({ headless: config.headless });
  const context = await browser.newContext({
    ...(await hasStoredSession() ? { storageState: config.storageStatePath } : {}),
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

  const { browser, context, page } = await openAuthenticatedContext();
  const startedAt = Date.now();
  let imageUpload = imagePath ? "pending" : "not-requested";

  try {
    await ensureGroupPageReady(page, context, groupUrl);
    logger.info({ groupUrl, dryRun }, "Facebook group page ready for publishing");

    const composer = await openComposerWithRecovery(page, context, groupUrl);
    const publishDialog = page.locator('[role="dialog"]').first();
    const dialogWasVisible = await isVisible(publishDialog);
    await composer.fill(text);

    if (imagePath) {
      try {
        const uploadResult = await uploadImage(page, imagePath, publishDialog);
        imageUpload = "uploaded";
        logger.info({ imagePath, uploadResult }, "Facebook image upload succeeded");
      } catch (error) {
        imageUpload = "failed";
        const uploadErrorPath = path.join(
          config.artifactsDir,
          `facebook-upload-warning-${Date.now()}.png`
        );
        try {
          await page.screenshot({ path: uploadErrorPath, fullPage: true });
        } catch {
          // ignore screenshot failure
        }
        logger.warn(
          { err: error, imagePath, uploadErrorPath },
          "Facebook image upload failed; continuing without image"
        );
      }
    }

    if (appendText && appendText.trim()) {
      const activeComposer = page.locator('[role="dialog"] div[contenteditable="true"]').first();
      await activeComposer.waitFor({ state: "visible", timeout: 4000 });
      await waitForPreview(page);
      await activeComposer.press("End");
      await page.waitForTimeout(300);
      await activeComposer.type(appendText, { delay: 15 });
    }

    await waitForPreview(page);

    const screenshotPath = path.join(
      config.artifactsDir,
      `facebook-compose-${Date.now()}.png`
    );
    await page.screenshot({ path: screenshotPath, fullPage: true });

    if (dryRun) {
      await saveStorageState(context);
      logger.info({ screenshotPath }, "Dry run complete; not clicking Post");
      return {
        ok: true,
        mode: "dry-run",
        imageUpload,
        screenshotPath,
        elapsedMs: Date.now() - startedAt,
      };
    }

    const postButton = await clickPost(page);
    const publishResult = await waitForPublishConfirmation(page, {
      dialog: dialogWasVisible ? publishDialog : null,
      postButton,
    });
    await saveStorageState(context);

    return {
      ok: true,
      mode: "live",
      imageUpload,
      screenshotPath,
      publishConfirmation: publishResult,
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
