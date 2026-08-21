import webpush from "web-push";

export const DEFAULT_ALLOWED_ORIGIN = "https://kjkwon981229-prog.github.io";
export const DEFAULT_MAX_SUBSCRIPTIONS = 25;
export const MAX_BODY_BYTES = 16 * 1024;
const SUBSCRIPTION_PREFIX = "sub:";
const NOTIFICATION_PREFIX = "notify:";
const READY_STATE_PREFIX = "state:ready:";
const MARKER_TTL_SECONDS = 3 * 24 * 60 * 60;
// KV has no compare-and-set operation.  This isolate-local registry closes
// the same-isolate race; the deterministic KV marker remains the guard across
// requests and isolates.  The workflow concurrency group limits the producer
// side to one active daily run.
const inFlightNotifications = new Map();
const inFlightSubscriptionWrites = new Map();

const encoder = new TextEncoder();

function configuredOrigin(env) {
  return String(env?.ALLOWED_ORIGIN || DEFAULT_ALLOWED_ORIGIN).replace(/\/$/, "");
}

function jsonResponse(request, env, body, status = 200, extraHeaders = {}) {
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "Vary": "Origin",
    ...extraHeaders,
  });
  const origin = request.headers.get("Origin");
  if (origin === configuredOrigin(env)) {
    headers.set("Access-Control-Allow-Origin", origin);
  }
  return new Response(JSON.stringify(body), { status, headers });
}

function emptyResponse(request, env, status = 204) {
  const headers = new Headers({
    "Cache-Control": "no-store",
    "Vary": "Origin",
    "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type",
    "Access-Control-Max-Age": "86400",
  });
  const origin = request.headers.get("Origin");
  if (origin === configuredOrigin(env)) {
    headers.set("Access-Control-Allow-Origin", origin);
  }
  return new Response(null, { status, headers });
}

function originIsAllowed(request, env, { allowMissing = false } = {}) {
  const origin = request.headers.get("Origin");
  return origin === configuredOrigin(env) || (allowMissing && !origin);
}

function errorResponse(request, env, status, code) {
  return jsonResponse(request, env, { ok: false, error: code }, status);
}

function hasKv(env) {
  return Boolean(env?.PUSH_SUBSCRIPTIONS && typeof env.PUSH_SUBSCRIPTIONS.get === "function");
}

function hasVapidConfig(env) {
  if (!env?.VAPID_PUBLIC_KEY || !env?.VAPID_PRIVATE_KEY || !env?.VAPID_SUBJECT) {
    return false;
  }
  try {
    return decodeBase64Url(String(env.VAPID_PUBLIC_KEY)).byteLength === 65 && decodeBase64Url(String(env.VAPID_PRIVATE_KEY)).byteLength === 32;
  } catch {
    return false;
  }
}

function isBase64Url(value) {
  return typeof value === "string" && /^[A-Za-z0-9_-]+$/.test(value) && value.length > 0;
}

function decodeBase64Url(value) {
  if (!isBase64Url(value)) {
    throw new Error("invalid base64url");
  }
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function validateSubscription(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  if (typeof value.endpoint !== "string" || value.endpoint.length > 2048) {
    return null;
  }
  let endpoint;
  try {
    endpoint = new URL(value.endpoint);
  } catch {
    return null;
  }
  if (endpoint.protocol !== "https:" || endpoint.username || endpoint.password) {
    return null;
  }
  const keys = value.keys;
  if (!keys || typeof keys !== "object" || Array.isArray(keys)) {
    return null;
  }
  try {
    if (decodeBase64Url(keys.p256dh).byteLength !== 65) {
      return null;
    }
    if (decodeBase64Url(keys.auth).byteLength !== 16) {
      return null;
    }
  } catch {
    return null;
  }
  return {
    endpoint: endpoint.toString(),
    keys: { p256dh: keys.p256dh, auth: keys.auth },
  };
}

async function readJson(request) {
  const contentLength = Number(request.headers.get("Content-Length") || 0);
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_BYTES) {
    return null;
  }
  const bytes = new Uint8Array(await request.arrayBuffer());
  if (bytes.byteLength > MAX_BODY_BYTES) {
    return null;
  }
  try {
    return JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
}

async function endpointKey(endpoint) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(endpoint));
  return `${SUBSCRIPTION_PREFIX}${Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("")}`;
}

function requestPath(request) {
  const path = new URL(request.url).pathname;
  return path.length > 1 ? path.replace(/\/+$/, "") : path;
}

function validDate(value) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function validRunId(value) {
  return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
}

function validNotificationType(value) {
  return value === "READY" || value === "FAILURE";
}

function validNotificationSource(value) {
  return value === "schedule" || value === "manual" || value === "other";
}

export function deliveryState({ subscriptionCount, sent, failed, pruned }) {
  if (subscriptionCount === 0) {
    return "NO_SUBSCRIBERS";
  }
  if (sent === 0 && failed === 0 && pruned > 0) {
    return "STALE_SUBSCRIPTIONS_PRUNED";
  }
  if (sent === 0 && failed > 0) {
    return "ALL_DELIVERIES_FAILED";
  }
  if (sent > 0 && failed > 0) {
    return "PARTIAL_DELIVERY";
  }
  if (sent > 0) {
    return "DELIVERED";
  }
  return "REQUEST_ACCEPTED";
}

const DELIVERY_STATES = new Set([
  "DELIVERED",
  "NO_SUBSCRIBERS",
  "PARTIAL_DELIVERY",
  "ALL_DELIVERIES_FAILED",
  "STALE_SUBSCRIPTIONS_PRUNED",
]);

function nonNegativeCount(value) {
  const count = Number(value);
  return Number.isFinite(count) && count >= 0 ? Math.trunc(count) : 0;
}

function normalizeStoredMarker(marker) {
  const sent = nonNegativeCount(marker?.sent);
  const failed = nonNegativeCount(marker?.failed);
  const pruned = nonNegativeCount(marker?.pruned);
  const subscriptionCount = Number.isFinite(Number(marker?.subscription_count))
    ? nonNegativeCount(marker.subscription_count)
    : sent + failed + pruned;
  const deliveryStateValue = DELIVERY_STATES.has(marker?.delivery_state)
    ? marker.delivery_state
    : deliveryState({ subscriptionCount, sent, failed, pruned });
  return {
    delivery_state: deliveryStateValue,
    subscription_count: subscriptionCount,
    sent,
    failed,
    pruned,
  };
}

function notificationMarkerKey(date, type, source, runId = "") {
  if (source === "manual") {
    return `${NOTIFICATION_PREFIX}${date}:${type}:${source}:${runId}`;
  }
  return `${NOTIFICATION_PREFIX}${date}:${type}:${source}`;
}

function legacyNotificationMarkerKey(date, type) {
  return `${NOTIFICATION_PREFIX}${date}:${type}`;
}

function notificationPayload(type, env, { source = "other", runId = "" } = {}) {
  const ready = type === "READY";
  const baseTag = ready ? "insight-desk-ready" : "insight-desk-failure";
  return {
    title: ready ? "오늘 브리핑 준비 완료" : "오늘 브리핑 업데이트 실패",
    body: ready ? "Insight Desk 오늘 브리핑을 확인하세요." : "마지막 정상 브리핑을 유지하고 있습니다.",
    tag: source === "manual" && runId ? `${baseTag}-${runId}` : baseTag,
    url: `${configuredOrigin(env)}/insight-desk/`,
  };
}

function errorStatus(error) {
  const status = Number(error?.statusCode || error?.status || 0);
  return Number.isInteger(status) ? status : 0;
}

async function sendWebPush(subscription, payload, env) {
  return webpush.sendNotification(subscription, JSON.stringify(payload), {
    TTL: 60 * 60 * 24,
    urgency: "normal",
    contentEncoding: "aes128gcm",
    timeout: 8_000,
    vapidDetails: {
      subject: String(env.VAPID_SUBJECT),
      publicKey: String(env.VAPID_PUBLIC_KEY),
      privateKey: String(env.VAPID_PRIVATE_KEY),
    },
  });
}

async function listSubscriptionKeys(kv, maxSubscriptions) {
  const keys = [];
  let cursor;
  while (keys.length < maxSubscriptions) {
    const page = await kv.list({
      prefix: SUBSCRIPTION_PREFIX,
      limit: Math.min(25, maxSubscriptions - keys.length),
      ...(cursor ? { cursor } : {}),
    });
    for (const key of page.keys || []) {
      if (key?.name) {
        keys.push(key.name);
      }
    }
    if (page.list_complete !== false || !page.cursor) {
      break;
    }
    cursor = page.cursor;
  }
  return keys;
}

async function dispatchNotificationOnce(env, requestPayload, dependencies = {}) {
  if (!hasKv(env)) {
    throw new Error("KV_NOT_CONFIGURED");
  }
  if (!hasVapidConfig(env)) {
    throw new Error("VAPID_NOT_CONFIGURED");
  }
  const { date, run_id: runId, type, source } = requestPayload;
  // Scheduled delivery is idempotent for the day. Manual workflow runs
  // are idempotent per run so a fresh operator-triggered validation can emit
  // its own result without consuming or being consumed by another run.
  const markerKey = notificationMarkerKey(date, type, source, runId);
  let existing = await env.PUSH_SUBSCRIPTIONS.get(markerKey);
  // Pre-source legacy markers correspond to the old generic caller only.
  // They must never suppress a new explicit manual run.
  if (!existing && source === "other") {
    existing = await env.PUSH_SUBSCRIPTIONS.get(legacyNotificationMarkerKey(date, type));
  }
  if (existing) {
    let marker = {};
    try {
      marker = JSON.parse(existing);
    } catch {
      marker = {};
    }
    const normalized = normalizeStoredMarker(marker);
    return {
      ok: normalized.delivery_state === "DELIVERED",
      duplicate: true,
      request_state: "REQUEST_ACCEPTED",
      date,
      type,
      source: marker.source || source,
      ...normalized,
    };
  }

  await env.PUSH_SUBSCRIPTIONS.put(
    markerKey,
    JSON.stringify({ state: "sending", date, type, source, run_id: runId, at: new Date().toISOString() }),
    { expirationTtl: MARKER_TTL_SECONDS },
  );
  const send = dependencies.sendNotification || sendWebPush;
  const keys = await listSubscriptionKeys(
    env.PUSH_SUBSCRIPTIONS,
    Number(env.MAX_SUBSCRIPTIONS || DEFAULT_MAX_SUBSCRIPTIONS),
  );
  const payload = notificationPayload(type, env, { source, runId });
  let sent = 0;
  let failed = 0;
  let pruned = 0;
  try {
    for (const key of keys) {
      const raw = await env.PUSH_SUBSCRIPTIONS.get(key);
      let subscription;
      try {
        subscription = validateSubscription(raw ? JSON.parse(raw) : null);
      } catch {
        subscription = null;
      }
      if (!subscription) {
        await env.PUSH_SUBSCRIPTIONS.delete(key);
        pruned += 1;
        continue;
      }
      try {
        await send(subscription, payload, env);
        sent += 1;
      } catch (error) {
        failed += 1;
        if (errorStatus(error) === 404 || errorStatus(error) === 410) {
          await env.PUSH_SUBSCRIPTIONS.delete(key);
          pruned += 1;
        }
      }
    }
    const subscriptionCount = keys.length;
    const state = deliveryState({ subscriptionCount, sent, failed, pruned });
    const marker = {
      state: "complete",
      request_state: "REQUEST_ACCEPTED",
      delivery_state: state,
      date,
      type,
      source,
      run_id: runId,
      subscription_count: subscriptionCount,
      sent,
      failed,
      pruned,
      at: new Date().toISOString(),
    };
    await env.PUSH_SUBSCRIPTIONS.put(markerKey, JSON.stringify(marker), { expirationTtl: MARKER_TTL_SECONDS });
    if (type === "READY" && state !== "ALL_DELIVERIES_FAILED" && state !== "PARTIAL_DELIVERY") {
      await env.PUSH_SUBSCRIPTIONS.put(
        `${READY_STATE_PREFIX}${date}`,
        JSON.stringify({
          run_id: runId,
          source,
          delivery_state: state,
          subscription_count: subscriptionCount,
          sent,
          failed,
          pruned,
          at: new Date().toISOString(),
        }),
        { expirationTtl: MARKER_TTL_SECONDS },
      );
    }
    return {
      ok: state === "DELIVERED",
      duplicate: false,
      request_state: "REQUEST_ACCEPTED",
      date,
      type,
      source,
      delivery_state: state,
      subscription_count: subscriptionCount,
      sent,
      failed,
      pruned,
    };
  } catch (error) {
    await env.PUSH_SUBSCRIPTIONS.delete(markerKey);
    throw error;
  }
}

async function dispatchNotification(env, requestPayload, dependencies = {}) {
  const { date, run_id: runId, type, source } = requestPayload;
  const markerKey = notificationMarkerKey(date, type, source, runId);
  const active = inFlightNotifications.get(markerKey);
  if (active) {
    const result = await active;
    return { ...result, duplicate: true };
  }
  const operation = dispatchNotificationOnce(env, requestPayload, dependencies);
  inFlightNotifications.set(markerKey, operation);
  try {
    return await operation;
  } finally {
    if (inFlightNotifications.get(markerKey) === operation) {
      inFlightNotifications.delete(markerKey);
    }
  }
}

async function serializeSubscriptionWrite(operation) {
  // KV cannot perform an atomic conditional write.  Serialize the local
  // count/read/write window so concurrent requests in one isolate cannot
  // exceed MAX_SUBSCRIPTIONS; cross-isolate enforcement still relies on the
  // platform's KV consistency and remains deliberately bounded.
  const key = "subscription-write";
  const previous = inFlightSubscriptionWrites.get(key);
  const waitForPrevious = previous ? previous.catch(() => undefined) : Promise.resolve();
  const current = waitForPrevious.then(operation);
  inFlightSubscriptionWrites.set(key, current);
  try {
    return await current;
  } finally {
    if (inFlightSubscriptionWrites.get(key) === current) {
      inFlightSubscriptionWrites.delete(key);
    }
  }
}

function validateSendPayload(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  if (!validDate(value.date) || !validRunId(value.run_id) || !validNotificationType(value.type)) {
    return null;
  }
  const source = value.source === undefined ? "other" : value.source;
  if (!validNotificationSource(source)) {
    return null;
  }
  return { date: value.date, run_id: value.run_id, type: value.type, source };
}

function authMatches(request, env) {
  const expected = String(env?.PUSH_SEND_TOKEN || "");
  const actual = request.headers.get("Authorization") || "";
  return Boolean(expected) && actual === `Bearer ${expected}`;
}

export function kstDate(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = Object.fromEntries(parts.filter((part) => part.type !== "literal").map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export async function runWatchdog(env, dependencies = {}) {
  if (!hasKv(env) || !hasVapidConfig(env)) {
    return { ok: false, skipped: true, reason: "CONFIG_NOT_READY" };
  }
  const now = dependencies.now ? dependencies.now() : new Date();
  const date = kstDate(now);
  const readyMarker = await env.PUSH_SUBSCRIPTIONS.get(`${READY_STATE_PREFIX}${date}`);
  if (readyMarker) {
    try {
      const ready = JSON.parse(readyMarker);
      if (ready.source === "schedule" && ready.delivery_state === "DELIVERED") {
        return { ok: true, skipped: true, reason: "READY_ALREADY_RECORDED", date };
      }
    } catch {
      // Legacy/manual markers do not prove that today's scheduled run ran.
    }
  }
  return dispatchNotification(
    env,
    { date, run_id: `watchdog-${date}`, type: "FAILURE", source: "schedule" },
    dependencies,
  );
}

export async function handleRequest(request, env, _context, dependencies = {}) {
  const method = request.method.toUpperCase();
  const path = requestPath(request);
  if (method === "OPTIONS") {
    if (!originIsAllowed(request, env)) {
      return errorResponse(request, env, 403, "ORIGIN_NOT_ALLOWED");
    }
    return emptyResponse(request, env);
  }

  if (path === "/health" && method === "GET") {
    if (!originIsAllowed(request, env, { allowMissing: true })) {
      return errorResponse(request, env, 403, "ORIGIN_NOT_ALLOWED");
    }
    return jsonResponse(request, env, {
      ok: true,
      service: "insight-desk-push",
      kv_configured: hasKv(env),
      vapid_configured: hasVapidConfig(env),
    });
  }

  if (path === "/vapid-public-key" && method === "GET") {
    if (!originIsAllowed(request, env, { allowMissing: true })) {
      return errorResponse(request, env, 403, "ORIGIN_NOT_ALLOWED");
    }
    if (!hasVapidConfig(env)) {
      return errorResponse(request, env, 503, "VAPID_NOT_CONFIGURED");
    }
    return jsonResponse(request, env, { ok: true, public_key: String(env.VAPID_PUBLIC_KEY) });
  }

  if (path === "/subscribe" && (method === "POST" || method === "DELETE")) {
    if (!originIsAllowed(request, env) || !hasKv(env)) {
      return errorResponse(request, env, !originIsAllowed(request, env) ? 403 : 503, !originIsAllowed(request, env) ? "ORIGIN_NOT_ALLOWED" : "KV_NOT_CONFIGURED");
    }
    const value = await readJson(request);
    const subscription = validateSubscription(value);
    if (!subscription) {
      return errorResponse(request, env, 400, "INVALID_SUBSCRIPTION");
    }
    const key = await endpointKey(subscription.endpoint);
    if (method === "DELETE") {
      return serializeSubscriptionWrite(async () => {
        await env.PUSH_SUBSCRIPTIONS.delete(key);
        return jsonResponse(request, env, { ok: true, subscribed: false });
      });
    }
    return serializeSubscriptionWrite(async () => {
      const maxSubscriptions = Math.max(1, Math.min(100, Number(env.MAX_SUBSCRIPTIONS || DEFAULT_MAX_SUBSCRIPTIONS)));
      const existing = await env.PUSH_SUBSCRIPTIONS.get(key);
      if (!existing && (await listSubscriptionKeys(env.PUSH_SUBSCRIPTIONS, maxSubscriptions + 1)).length >= maxSubscriptions) {
        return errorResponse(request, env, 429, "SUBSCRIPTION_LIMIT");
      }
      await env.PUSH_SUBSCRIPTIONS.put(key, JSON.stringify(subscription));
      return jsonResponse(request, env, { ok: true, subscribed: true }, 201);
    });
  }

  if (path === "/send" && method === "POST") {
    if (!authMatches(request, env)) {
      return errorResponse(request, env, 401, "SEND_AUTH_REQUIRED");
    }
    const payload = validateSendPayload(await readJson(request));
    if (!payload) {
      return errorResponse(request, env, 400, "INVALID_NOTIFICATION");
    }
    try {
      const result = await dispatchNotification(env, payload, dependencies);
      const status = result.ok ? 200 : result.delivery_state === "NO_SUBSCRIBERS" ? 202 : 502;
      return jsonResponse(request, env, result, status);
    } catch (error) {
      const code = error?.message === "VAPID_NOT_CONFIGURED" ? "VAPID_NOT_CONFIGURED" : error?.message === "KV_NOT_CONFIGURED" ? "KV_NOT_CONFIGURED" : "DELIVERY_FAILED";
      return errorResponse(request, env, code === "DELIVERY_FAILED" ? 502 : 503, code);
    }
  }

  return errorResponse(request, env, 404, "NOT_FOUND");
}

const worker = {
  async fetch(request, env, context) {
    return handleRequest(request, env, context);
  },
  async scheduled(_controller, env) {
    await runWatchdog(env);
  },
};

export default worker;
