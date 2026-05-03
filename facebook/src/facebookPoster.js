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

const COMMENT_BUTTON_PATTERNS = /comment|leave a comment|write a comment|תגובה|הגב|כתיבת תגובה/i;

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

async function firstVisibleLocator(candidates, timeout = 3000) {
  for (const candidate of candidates) {
    try {
      await candidate.waitFor({ state: "visible", timeout });
      return candidate;
    } catch {
      // try next candidate
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

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function compactWhitespace(value) {
  return value.replace(/\s+/g, " ").trim();
}

function snippetFromText(value, maxLength = 80) {
  const compact = compactWhitespace(value);
  if (!compact) {
    return "";
  }
  return compact.slice(0, maxLength).trim();
}

function preferredSnippet(value, maxLength = 80) {
  const firstNonEmptyLine = value
    .split("\n")
    .map((line) => compactWhitespace(line))
    .find((line) => line.length >= 12);
  return snippetFromText(firstNonEmptyLine || value, maxLength);
}

async function locatorText(locator) {
  try {
    return compactWhitespace(await locator.innerText());
  } catch {
    return compactWhitespace((await locator.textContent()) || "");
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

async function firstUsableUploadScope(composer, dialog) {
  const scopeCandidates = [
    dialog,
    composer.locator("xpath=ancestor::*[@role='dialog'][1]"),
    composer.locator("xpath=ancestor::form[1]"),
    composer.locator("xpath=ancestor::*[@role='article'][1]"),
    composer.locator("xpath=ancestor::div[.//div[@contenteditable='true']][1]"),
  ].filter(Boolean);

  for (const scope of scopeCandidates) {
    try {
      await scope.waitFor({ state: "visible", timeout: 1200 });
      const composerCount = await scope.locator('div[contenteditable="true"]').count();
      if (composerCount > 0) {
        return scope;
      }
    } catch {
      // try next scope
    }
  }

  throw new Error("Could not determine a safe Facebook composer scope for image upload");
}

async function bottomComposerIconButtons(scope) {
  const candidates = scope.locator('div[role="button"], button');
  const count = await candidates.count();
  const bottomButtons = [];

  for (let index = 0; index < count; index += 1) {
    const locator = candidates.nth(index);
    try {
      if (!(await locator.isVisible())) {
        continue;
      }
    } catch {
      continue;
    }

    const box = await locator.boundingBox();
    if (!box) {
      continue;
    }

    if (box.y < 450 || box.width > 120 || box.height > 120) {
      continue;
    }

    const svgCount = await locator.locator("svg").count();
    if (svgCount === 0) {
      continue;
    }

    bottomButtons.push({ locator, x: box.x, y: box.y });
  }

  return bottomButtons
    .sort((a, b) => b.y - a.y || a.x - b.x)
    .map((entry) => entry.locator);
}

async function uploadImage(page, imagePath, composer, dialog) {
  if (!imagePath) {
    return;
  }

  const resolved = path.resolve(imagePath);
  if (!(await exists(resolved))) {
    throw new Error(`Image file not found: ${resolved}`);
  }

  const uploadScope = await firstUsableUploadScope(composer, dialog);
  const initialImageCount = await uploadScope.locator("img").count();
  let directFileInput = await firstAttached(uploadScope, FILE_INPUT_SELECTORS, 1200);
  if (directFileInput != null) {
    return setFilesAndConfirm(
      page,
      uploadScope,
      directFileInput,
      resolved,
      initialImageCount,
    );
  }

  const uploadCandidates = [
    uploadScope.getByRole("button", { name: /photo|image|video|photo\/video|תמונה|תמונות|וידאו|סרטון/i }).first(),
    uploadScope.getByText(/photo|image|video|photo\/video|תמונה|תמונות|וידאו|סרטון/i).first(),
    uploadScope.locator('[aria-label*="photo"], [aria-label*="image"], [aria-label*="video"], [aria-label*="תמונה"], [aria-label*="וידאו"]').first(),
  ];

  const iconButtons = await bottomComposerIconButtons(uploadScope);
  const buttonCandidates = [...uploadCandidates, ...iconButtons];
  logger.info(
    { imagePath: resolved, candidateCount: buttonCandidates.length },
    "Trying Facebook image upload controls within composer scope"
  );

  for (const candidate of buttonCandidates) {
    try {
      await candidate.waitFor({ state: "visible", timeout: 1200 });
    } catch {
      continue;
    }

    try {
      try {
        const fileChooserPromise = page.waitForEvent("filechooser", { timeout: 3500 });
        await candidate.click({ force: true });
        const chooser = await fileChooserPromise;
        await chooser.setFiles(resolved);
        return waitForImageAttachment(page, uploadScope, initialImageCount);
      } catch {
        await candidate.click({ force: true });
      }

      let fileInput = await firstAttached(uploadScope, FILE_INPUT_SELECTORS, 2500);
      if (fileInput != null) {
        return await setFilesAndConfirm(
          page,
          uploadScope,
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

  directFileInput = await firstAttached(uploadScope, FILE_INPUT_SELECTORS, 1000);
  if (directFileInput != null) {
    return setFilesAndConfirm(
      page,
      uploadScope,
      directFileInput,
      resolved,
      initialImageCount,
    );
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

async function selectIdentityCandidate(pageNamePattern, candidates) {
  for (const candidate of candidates) {
    try {
      await candidate.waitFor({ state: "visible", timeout: 1500 });
      await candidate.click({ force: true });
      return true;
    } catch {
      // try next candidate
    }
  }

  const directOption = page.getByText(pageNamePattern).first();
  if (await isVisible(directOption)) {
    await directOption.click({ force: true });
    return true;
  }

  return false;
}

async function ensurePostingIdentity(page, dialog) {
  const pageName = config.postAsPageName?.trim();
  if (!pageName) {
    return { mode: "profile-default" };
  }

  const pageNamePattern = new RegExp(escapeRegExp(pageName), "i");
  const selectedIdentity = dialog.getByText(pageNamePattern).first();
  if (await isVisible(selectedIdentity)) {
    return { mode: "page-already-selected", pageName };
  }

  const identitySwitchers = [
    dialog.getByRole("button", { name: /switch profile|switch identity|post as|choose identity|בחר|זהות|פרופיל|page|דף/i }).first(),
    dialog.locator('[role="button"][aria-haspopup="menu"]').first(),
    dialog.locator('[role="button"][aria-label*="switch"]').first(),
    dialog.locator('[role="button"][aria-label*="profile"]').first(),
    dialog.locator('[role="button"][aria-label*="identity"]').first(),
    dialog.locator('[role="button"][aria-label*="דף"]').first(),
    dialog.locator('[role="button"][aria-label*="פרופיל"]').first(),
    dialog.locator('[role="button"]').filter({ has: dialog.getByText(/private group|public group|קבוצה פרטית|קבוצה ציבורית/i).first() }).first(),
  ];

  const opened = await selectIdentityCandidate(pageNamePattern, identitySwitchers);
  if (!opened) {
    throw new Error(`Configured Facebook page '${pageName}' was not selectable from the composer`);
  }

  const pageOptions = [
    page.getByRole("menuitem", { name: pageNamePattern }).first(),
    page.getByRole("button", { name: pageNamePattern }).first(),
    page.getByText(pageNamePattern).first(),
  ];

  let selected = false;
  for (const option of pageOptions) {
    try {
      await option.waitFor({ state: "visible", timeout: 3000 });
      await option.click({ force: true });
      selected = true;
      break;
    } catch {
      // try next option
    }
  }

  if (!selected) {
    throw new Error(`Facebook page option '${pageName}' did not appear after opening the identity switcher`);
  }

  await page.waitForTimeout(1500);
  const selectedAfterSwitch = dialog.getByText(pageNamePattern).first();
  if (!(await isVisible(selectedAfterSwitch))) {
    throw new Error(`Facebook composer did not confirm page identity '${pageName}' after selection`);
  }

  return { mode: "page-selected", pageName };
}

async function prepareComposerForPublish(page, context, groupUrl) {
  await ensureGroupPageReady(page, context, groupUrl);
  logger.info({ groupUrl }, "Facebook group page ready for publishing");

  const composer = await openComposerWithRecovery(page, context, groupUrl);
  const publishDialog = page.locator('[role="dialog"]').first();
  const dialogWasVisible = await isVisible(publishDialog);
  const identityResult = await ensurePostingIdentity(page, dialogWasVisible ? publishDialog : page);
  logger.info(
    { groupUrl, identityMode: identityResult.mode, pageName: identityResult.pageName || null },
    "Facebook publishing identity ready"
  );

  return { composer, publishDialog, dialogWasVisible, identityResult };
}

export async function primePostingIdentity(page, context, groupUrl) {
  if (!groupUrl) {
    throw new Error("groupUrl is required to prime Facebook posting identity");
  }

  const startedAt = Date.now();
  const { identityResult } = await prepareComposerForPublish(page, context, groupUrl);
  const screenshotPath = path.join(
    config.artifactsDir,
    `facebook-identity-ready-${Date.now()}.png`
  );
  await page.screenshot({ path: screenshotPath, fullPage: true });
  await saveStorageState(context);

  return {
    ok: true,
    groupUrl,
    identityMode: identityResult.mode,
    pageName: identityResult.pageName || null,
    screenshotPath,
    elapsedMs: Date.now() - startedAt,
  };
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

async function findPublishedPostArticle(page, text) {
  const snippet = preferredSnippet(text);
  if (!snippet) {
    throw new Error("Could not build a reliable text snippet to locate the published Facebook post");
  }

  const normalizedSnippet = snippet.toLowerCase();
  const deadline = Date.now() + config.postLocateTimeoutMs;

  while (Date.now() < deadline) {
    const articles = page.locator('[role="article"]');
    const count = Math.min(await articles.count(), 8);

    for (let index = 0; index < count; index += 1) {
      const article = articles.nth(index);
      if (!(await isVisible(article))) {
        continue;
      }

      const articleText = (await locatorText(article)).toLowerCase();
      if (articleText.includes(normalizedSnippet)) {
        return { article, snippet };
      }
    }

    await page.waitForTimeout(500);
  }

  throw new Error(`Could not find the published Facebook post using snippet '${snippet}'`);
}

async function openCommentComposer(page, article) {
  const commentButton = await firstVisibleLocator(
    [
      article.getByRole("button", { name: COMMENT_BUTTON_PATTERNS }).first(),
      article.locator(
        '[aria-label*="Comment"], [aria-label*="comment"], [aria-label*="תגובה"], [aria-label*="הגב"]'
      ).first(),
      article.getByText(COMMENT_BUTTON_PATTERNS).first(),
    ],
    2500
  );

  if (commentButton == null) {
    throw new Error("Could not find the comment button on the published Facebook post");
  }

  await commentButton.click({ force: true });
  await page.waitForTimeout(800);

  const composer = await firstVisibleLocator(
    [
      article.locator('div[role="textbox"][contenteditable="true"]').last(),
      page.locator('div[role="dialog"] div[role="textbox"][contenteditable="true"]').last(),
      page.locator('div[contenteditable="true"][aria-label*="comment"]').last(),
      page.locator('div[contenteditable="true"][aria-label*="Comment"]').last(),
      page.locator('div[contenteditable="true"][aria-label*="תגובה"]').last(),
    ],
    4000
  );

  if (composer == null) {
    throw new Error("Could not open the Facebook comment composer");
  }

  return composer;
}

async function waitForCommentConfirmation(page, article, commentText, composer) {
  const snippet = preferredSnippet(
    commentText
      .split("\n")
      .find((line) => line.includes("http")) || commentText
  );
  if (!snippet) {
    return { confirmation: "comment-submitted-without-snippet" };
  }

  const normalizedSnippet = snippet.toLowerCase();
  const deadline = Date.now() + config.commentConfirmTimeoutMs;

  while (Date.now() < deadline) {
    const articleText = (await locatorText(article)).toLowerCase();
    if (articleText.includes(normalizedSnippet)) {
      return { confirmation: "comment-visible", details: snippet };
    }

    try {
      const composerText = await locatorText(composer);
      if (!composerText) {
        return { confirmation: "composer-cleared", details: snippet };
      }
    } catch {
      return { confirmation: "composer-dismissed", details: snippet };
    }

    await page.waitForTimeout(400);
  }

  throw new Error(`Facebook comment submit was not confirmed for snippet '${snippet}'`);
}

async function publishCommentOnPost(page, text, commentText) {
  const { article, snippet: postSnippet } = await findPublishedPostArticle(page, text);
  const composer = await openCommentComposer(page, article);
  await composer.fill(commentText);
  await page.waitForTimeout(300);
  await composer.press("Enter");
  const commentConfirmation = await waitForCommentConfirmation(page, article, commentText, composer);

  return {
    postSnippet,
    commentConfirmation,
  };
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
  commentText = "",
  commentOnPost = false,
  keepOpenMs = 0,
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
    const { composer, publishDialog, dialogWasVisible } = await prepareComposerForPublish(
      page,
      context,
      groupUrl
    );
    logger.info({ groupUrl, dryRun }, "Facebook group page ready for publish submit");
    await composer.fill(text);

    if (imagePath) {
      try {
        const uploadResult = await uploadImage(
          page,
          imagePath,
          composer,
          dialogWasVisible ? publishDialog : null,
        );
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
    let commentResult = null;
    if (commentOnPost && commentText.trim()) {
      await page.waitForTimeout(1500);
      commentResult = await publishCommentOnPost(page, text, commentText);
    }
    await saveStorageState(context);

    return {
      ok: true,
      mode: "live",
      imageUpload,
      screenshotPath,
      publishConfirmation: publishResult,
      commentResult,
      keepOpenMs,
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
    if (keepOpenMs > 0) {
      logger.info({ keepOpenMs }, "Keeping Facebook browser open for inspection");
      setTimeout(async () => {
        try {
          await browser.close();
        } catch {
          // ignore delayed browser close errors
        }
      }, keepOpenMs);
    } else {
      await browser.close();
    }
  }
}
