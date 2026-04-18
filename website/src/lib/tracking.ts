import { createHash, randomBytes, timingSafeEqual } from "node:crypto";
import type { NextRequest } from "next/server";

const ALLOWED_TRACKING_HOST_PATTERNS = [
  /(^|\.)aliexpress\.com$/i,
  /(^|\.)aliexpress\.ru$/i,
];

export interface TrackingLinkPayload {
  idempotencyKey: string;
  targetUrl: string;
  dealId?: number | null;
  queueItemId?: number | null;
  platform?: string | null;
  destinationKey?: string | null;
  sourceGroup?: string | null;
  postVariant?: string | null;
  metadata?: Record<string, unknown> | null;
}

export function createTrackingToken(): string {
  return randomBytes(12).toString("base64url");
}

export function getTrackingBaseUrl(origin: string): string {
  const configured = process.env.TRACKING_BASE_URL?.trim();
  const baseUrl = configured || origin;
  return baseUrl.replace(/\/+$/, "");
}

export function buildTrackedUrl(baseUrl: string, token: string): string {
  return `${baseUrl}/go/${token}`;
}

export function validateTrackingPayload(raw: unknown): TrackingLinkPayload {
  if (!raw || typeof raw !== "object") {
    throw new Error("Invalid JSON payload");
  }

  const payload = raw as Record<string, unknown>;
  const idempotencyKey = normalizeText(payload.idempotencyKey, 200);
  const targetUrl = normalizeText(payload.targetUrl, 2000);

  if (!idempotencyKey) {
    throw new Error("idempotencyKey is required");
  }

  if (!targetUrl) {
    throw new Error("targetUrl is required");
  }

  const parsedTargetUrl = parseAllowedTargetUrl(targetUrl);

  return {
    idempotencyKey,
    targetUrl: parsedTargetUrl.toString(),
    dealId: normalizeNumber(payload.dealId),
    queueItemId: normalizeNumber(payload.queueItemId),
    platform: normalizeText(payload.platform, 100),
    destinationKey: normalizeText(payload.destinationKey, 100),
    sourceGroup: normalizeText(payload.sourceGroup, 255),
    postVariant: normalizeText(payload.postVariant, 100),
    metadata: normalizeMetadata(payload.metadata),
  };
}

export function parseAllowedTargetUrl(value: string): URL {
  const parsed = new URL(value);

  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("targetUrl must use http or https");
  }

  if (
    !ALLOWED_TRACKING_HOST_PATTERNS.some((pattern) =>
      pattern.test(parsed.hostname)
    )
  ) {
    throw new Error("targetUrl hostname is not allowed");
  }

  return parsed;
}

export function getClientIp(request: NextRequest): string | null {
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    const [firstIp] = forwardedFor.split(",");
    return firstIp?.trim() || null;
  }

  return request.headers.get("x-real-ip")?.trim() || null;
}

export function hashIp(ip: string | null): string | null {
  if (!ip) {
    return null;
  }

  const salt = process.env.TRACKING_IP_HASH_SALT?.trim();
  if (!salt) {
    return null;
  }

  return createHash("sha256").update(`${salt}:${ip}`).digest("hex");
}

export function getClickContext(request: NextRequest) {
  return {
    ipHash: hashIp(getClientIp(request)),
    userAgent: normalizeText(request.headers.get("user-agent"), 1000),
    referer: normalizeText(request.headers.get("referer"), 1000),
    countryCode: normalizeText(request.headers.get("cf-ipcountry"), 10),
    cfRay: normalizeText(request.headers.get("cf-ray"), 64),
  };
}

export function hasValidTrackingSecret(request: NextRequest): boolean {
  const expected = process.env.TRACKING_API_SECRET;
  if (!expected) {
    throw new Error("Missing required environment variable: TRACKING_API_SECRET");
  }

  const provided = request.headers.get("x-tracking-secret");
  if (!provided) {
    return false;
  }

  const expectedBuffer = Buffer.from(expected, "utf8");
  const providedBuffer = Buffer.from(provided, "utf8");

  if (expectedBuffer.length !== providedBuffer.length) {
    return false;
  }

  return timingSafeEqual(expectedBuffer, providedBuffer);
}

function normalizeText(
  value: unknown,
  maxLength: number
): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  return trimmed.slice(0, maxLength);
}

function normalizeNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
}

function normalizeMetadata(
  value: unknown
): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  return value as Record<string, unknown>;
}
